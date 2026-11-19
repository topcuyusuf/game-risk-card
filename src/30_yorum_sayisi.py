"""Adım 30: Oyun başına kaç yorum yeterli? (neden 200?)

Elimizdeki 200 yorumdan rastgele N tanesi seçilir (N = 25, 50, 100, 150, 200) ve kart yeniden kurulur.
  1) Başarı  : kart puanının ve modelin AUC'si (karanlık oyun) N ile nasıl değişiyor?
  2) Kararlılık: AYNI oyun, ORTAK YORUMU OLMAYAN iki ayrı N'lik örnekle iki kez puanlanır
                (N = 25, 50, 100; 200 yorumdan en çok 2 x 100 ayrık örnek çıkar).
                Renk aynı mı kalıyor? Puan ne kadar oynuyor?
Adil olsun diye modeller 5 katlı düzende eğitilir: her oyun, onu görmemiş bir modelle puanlanır.
Kural karnesi (hangi kural gösterilir, akran eşikleri) dondurulmuş sistemden alınır ve değişmez.
Kullanım:  python src/30_yorum_sayisi.py
"""

import importlib
import random
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold

import sistem as sistem_mod
from ortak import KOK, VERI

ilk_model = importlib.import_module("10_ilk_model")
risk = importlib.import_module("14_risk_skoru")
kanit_mod = importlib.import_module("15_kanitlar")
kart_mod = importlib.import_module("16_kart")

N_DEGERLERI = [25, 50, 100, 150, 200]
AYRIK_N = [25, 50, 100]
TEKRAR = 5


def puanla(modeller, oyun_id, yorumlar, karne, magaza):
    """Verilen yorumlarla tek oyunun kartı -> (kural puanı, kural rengi, genel olasılık)."""
    metin = [" ".join(yorumlar)]
    s = {ad: float(m.predict_proba(metin)[0, 1]) for ad, m in modeller.items()}
    s["renk"] = risk.renk(s["genel_olas"])
    ys = [{"metin": y, "yildiz": 1, "faydali_oy": 0} for y in yorumlar]   # sıra puanı etkilemez
    k = kart_mod.kart_kur(oyun_id, "", s, kanit_mod.oyun_kanitlari(ys, ""), karne, magaza)
    return k["puan"], k["renk"], s["genel_olas"]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    tablo = pd.read_pickle(VERI / "oyun_tablosu.pkl").reset_index(drop=True)
    _, _, _, _, magaza = kart_mod.oku()
    karne = sistem_mod.sistemi_yukle()["karne"]
    y_genel = risk.genel_karanlik(tablo)
    metin_tam = tablo["yorumlar"].map(" ".join)
    hedef = {"genel_olas": y_genel, "reklam_olas": tablo["t13"], "durdurma_olas": tablo["t28"]}

    # Katlar genel etikete göre (bilinmeyenler 'yok' gibi bölünür; sadece bölme için)
    katlar = StratifiedKFold(5, shuffle=True, random_state=42).split(tablo, y_genel.fillna(0))
    r = random.Random(42)
    sonuc, ayrik = [], []
    for kat, (egitim, sinav) in enumerate(katlar, 1):
        modeller = {}
        for ad, y in hedef.items():
            b = y.iloc[egitim].notna().to_numpy()
            modeller[ad] = ilk_model.model_kur().fit(metin_tam.iloc[egitim][b], y.iloc[egitim][b].astype(int))
        for i in sinav:
            oyun_id, yorumlar = tablo.at[i, "oyun_id"], tablo.at[i, "yorumlar"]
            m = magaza.get(oyun_id)
            for n in N_DEGERLERI:
                for t in range(TEKRAR if n < len(yorumlar) else 1):
                    ornek = r.sample(yorumlar, min(n, len(yorumlar)))
                    p, renk, g = puanla(modeller, oyun_id, ornek, karne, m)
                    sonuc.append({"oyun_id": oyun_id, "n": n, "tekrar": t, "puan": p, "renk": renk, "genel": g})
            for n in AYRIK_N:
                if len(yorumlar) < 2 * n:
                    continue
                for t in range(TEKRAR):
                    karisik = r.sample(yorumlar, 2 * n)
                    a = puanla(modeller, oyun_id, karisik[:n], karne, m)
                    b = puanla(modeller, oyun_id, karisik[n:], karne, m)
                    ayrik.append({"oyun_id": oyun_id, "n": n, "puan_a": a[0], "puan_b": b[0],
                                  "renk_a": a[1], "renk_b": b[1]})
        print(f"kat {kat}/5 bitti", flush=True)

    df = pd.DataFrame(sonuc).merge(pd.DataFrame({"oyun_id": tablo.oyun_id, "karanlik": y_genel}), on="oyun_id")
    ay = pd.DataFrame(ayrik)
    df.to_csv(VERI / "sonuclar_yorum_sayisi.csv", index=False, encoding="utf-8")
    ay.to_csv(VERI / "sonuclar_yorum_sayisi_ayrik.csv", index=False, encoding="utf-8")

    # 1) Başarı: her N ve tekrar için AUC, sonra tekrarların ortalaması
    b = df[df.karanlik.notna()]
    auc = b.groupby(["n", "tekrar"]).apply(lambda g: pd.Series({
        "kural": roc_auc_score(g.karanlik, g.puan), "model": roc_auc_score(g.karanlik, g.genel)}),
        include_groups=False).groupby("n").agg(["mean", "std"])
    renk_pay = b.groupby(["n", "renk"]).karanlik.mean().unstack()[["yesil", "sari", "kirmizi"]]
    print("\nBaşarı (AUC, 5 tekrar ortalaması ± sapma):")
    for n in N_DEGERLERI:
        print(f"  N={n:<4} kural puanı {auc.loc[n, ('kural', 'mean')]:.3f} ± {auc.loc[n, ('kural', 'std')]:.3f}"
              f" | model {auc.loc[n, ('model', 'mean')]:.3f} ± {auc.loc[n, ('model', 'std')]:.3f}"
              f" | karanlık payı yeşil/sarı/kırmızı: " + " / ".join(f"%{100 * v:.0f}" for v in renk_pay.loc[n]))

    # 2) Kararlılık: ayrık iki örnekte renk aynı mı, puan farkı ne?
    ay["ayni_renk"] = ay.renk_a == ay.renk_b
    ay["zit_renk"] = ay[["renk_a", "renk_b"]].apply(set, axis=1).map(lambda s: s == {"yesil", "kirmizi"})
    ay["fark"] = (ay.puan_a - ay.puan_b).abs()
    kar = ay.groupby("n").agg(ayni_renk=("ayni_renk", "mean"), zit_renk=("zit_renk", "mean"),
                              ort_fark=("fark", "mean"), fark_3_ustu=("fark", lambda f: (f >= 3).mean()))
    print("\nKararlılık (ortak yorumu olmayan iki örnek, aynı oyun):")
    print(kar.to_string(float_format=lambda v: f"{v:.2f}"))

    # Eğilim: renk aynı kalma oranı log(N) ile doğrusal mı? -> 200 ve 400 için kaba tahmin
    x, yv = np.log(kar.index.to_numpy(float)), kar.ayni_renk.to_numpy()
    e, k = np.polyfit(x, yv, 1)
    for n in (200, 400):
        print(f"  Eğilimle tahmin: N={n} -> renk aynı kalma ~%{100 * min(1, e * np.log(n) + k):.0f}")

    # Grafik
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 3.8))
    a1.errorbar(N_DEGERLERI, auc[("kural", "mean")], yerr=auc[("kural", "std")], marker="o", label="Rule score (card)")
    a1.errorbar(N_DEGERLERI, auc[("model", "mean")], yerr=auc[("model", "std")], marker="s", label="General model")
    a1.set_xlabel("Reviews per game"); a1.set_ylabel("AUC (dark game)"); a1.set_title("Accuracy vs number of reviews")
    a1.set_xticks(N_DEGERLERI); a1.legend(); a1.grid(alpha=.3)
    a2.plot(kar.index, 100 * kar.ayni_renk, marker="o", color="#2E7D4F")
    a2.set_xlabel("Reviews per sample"); a2.set_ylabel("Same colour (%)")
    a2.set_title("Stability: two separate samples of one game"); a2.set_xticks(AYRIK_N); a2.grid(alpha=.3)
    a2.set_ylim(0, 100)
    fig.tight_layout()
    fig.savefig(KOK / "cikti" / "grafikler" / "10_review_count.png", dpi=150)
    print("\n-> cikti/grafikler/10_review_count.png")


if __name__ == "__main__":
    main()
