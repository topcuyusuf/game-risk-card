"""Adım 38: 'Beklenen ekran süresi' göstergesi denemesi.

Soru: karta renk yerine oyuna özel bir süre tahmini ("bu oyunda kendi ortalamanın ~1.6 katı") koymak
renk başına ortalamadan daha iyi mi?
Veri: 35. adım (sıkı eşleşme, 44 oyun) + 37. adım (yeni 37 oyun) = 81 oyun; hedef log_rel.
Adaylar (hepsi birini-dışarıda-bırak, LOO):
  0) sabit      : herkese ortalama
  1) renk       : kartın rengine göre ortalama (şu anki kart cümlesi)
  2) model      : log_rel = a + b * genel model olasılığı
  3) model+puan : log_rel = a + b * model + c * tuzak puanı
Ölçüt: tahminin gerçeğe ortalama uzaklığı (log ölçekte MAE) ve sıra ilişkisi.
Ayrıca karttaki renk cümlesi için 81 oyunluk renk ölçeği data/sure_olcegi.json'a, Şekil 11 cikti/grafikler/'e yazılır.
Kullanım:  python src/38_beklenen_sure.py
"""

import importlib
import json
import sys

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import LinearRegression

from ortak import VERI

o35 = importlib.import_module("35_gercek_sure")     # grafik()

RENKLER = ["yesil", "sari", "kirmizi"]


def loo(e, tahminci):
    t = np.empty(len(e))
    for i in range(len(e)):
        egitim = e.drop(e.index[i])
        t[i] = tahminci(egitim, e.iloc[[i]])
    return t


def sabit(eg, te):
    return eg.log_rel.mean()


def renk(eg, te):
    return eg.groupby("kart").log_rel.mean().get(te.kart.iloc[0], eg.log_rel.mean())


def dogrusal(sutunlar):
    def f(eg, te):
        return LinearRegression().fit(eg[sutunlar], eg.log_rel).predict(te[sutunlar])[0]
    return f


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    a = pd.read_csv(VERI / "sonuclar_gercek_sure.csv").assign(kume="35_eslesen")
    b = pd.read_csv(VERI / "sonuclar_genis_sure.csv").assign(kume="37_yeni")
    s = ["anahtar", "kart", "puan", "model", "log_rel", "kume"]
    e = pd.concat([a[s], b[s]]).drop_duplicates("anahtar").reset_index(drop=True)
    print(f"Oyun: {len(e)} ({e.kume.value_counts().to_dict()})\n")

    print(f"{'Gösterge':<12}{'MAE (log)':>10}{'tipik hata':>12}{'rho':>7}")
    for ad, f in [("sabit", sabit), ("renk", renk), ("model", dogrusal(["model"])),
                  ("model+puan", dogrusal(["model", "puan"]))]:
        t = loo(e, f)
        mae = np.abs(t - e.log_rel).mean()
        # renk: LOO grup ortalamasında sıra ilişkisi yapay olarak negatife kayar; yalnız MAE anlamlı
        rho = spearmanr(t, e.log_rel)[0] if ad not in ("sabit", "renk") else float("nan")
        print(f"{ad:<12}{mae:>10.3f}{'×' + format(np.exp(mae), '.2f'):>12}{rho:>+7.2f}")

    m = LinearRegression().fit(e[["model"]], e.log_rel)
    print(f"\nmodel çizgisi: kat = exp({m.intercept_:+.2f} {m.coef_[0]:+.2f} × olasılık) "
          f"-> olasılık 0.2: ×{np.exp(m.intercept_ + .2 * m.coef_[0]):.2f}, "
          f"0.5: ×{np.exp(m.intercept_ + .5 * m.coef_[0]):.2f}, 0.8: ×{np.exp(m.intercept_ + .8 * m.coef_[0]):.2f}")

    # Kart cümlesi için renk ölçeği (81 oyun) + bootstrap aralığı
    r = np.random.default_rng(42)
    olcek, aralik = {}, {}
    print(f"\n{'Kart':<9}{'oyun':>5}{'kat':>7}   %95 aralık")
    for renk_ in RENKLER:
        v = e.loc[e.kart == renk_, "log_rel"].to_numpy()
        bs = [np.exp(r.choice(v, len(v)).mean()) for _ in range(2000)]
        olcek[renk_], aralik[renk_] = float(np.exp(v.mean())), [float(x) for x in np.percentile(bs, [2.5, 97.5])]
        print(f"{renk_:<9}{len(v):>5}{olcek[renk_]:>7.2f}   {aralik[renk_][0]:.2f} – {aralik[renk_][1]:.2f}")
    yk, yy = (e.loc[e.kart == k, "log_rel"].to_numpy() for k in ["kirmizi", "yesil"])
    fark = [np.exp(r.choice(yk, len(yk)).mean() - r.choice(yy, len(yy)).mean()) for _ in range(2000)]
    oran = float(np.exp(yk.mean() - yy.mean()))
    print(f"Kırmızı / yeşil: {oran:.2f} kat (%95 {np.percentile(fark, 2.5):.2f} – {np.percentile(fark, 97.5):.2f})")
    json.dump({"kat": olcek, "aralik": aralik, "kirmizi_yesil": oran, "oyun": int(len(e))},
              open(VERI / "sure_olcegi.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("-> data/sure_olcegi.json")
    e["kat"] = np.exp(e.log_rel)
    o35.grafik(e, olcek, aralik)


if __name__ == "__main__":
    main()
