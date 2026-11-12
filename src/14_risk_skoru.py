"""Adım 14: Risk kartının sayısal kısmı — genel risk puanı ve iki özel tuzak puanı.

Her oyun için, o oyunu HİÇ GÖRMEMİŞ modelin verdiği olasılıklar hesaplanır (5 katlı):
  genel_olas   : oyun genel olarak 'karanlık' mı? (14 etiketin çoğunluğu)
  reklam_olas  : Advertisements var mı?
  durdurma_olas: Can't Pause or Save var mı?
Sonra olasılıkların 'dürüst' olup olmadığı (kalibrasyon) kontrol edilir.
Kullanım:  python src/14_risk_skoru.py
"""

import importlib

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import KFold

from ortak import HEDEF_TUZAKLAR, VERI

ilk_model = importlib.import_module("10_ilk_model")
SUTUNLAR = [f"t{t}" for t in HEDEF_TUZAKLAR]
CIKTI = VERI / "risk_skorlari.csv"

# Renk eşikleri: kalibrasyon tablosuna bakılarak seçildi (ham model puanı üzerinde).
SARI_ESIK = 0.40
KIRMIZI_ESIK = 0.60


def renk(olas):
    """Ham genel risk puanını renge çevirir."""
    if olas >= KIRMIZI_ESIK:
        return "kirmizi"
    if olas >= SARI_ESIK:
        return "sari"
    return "yesil"


def genel_karanlik(tablo):
    """14 etiketin bilinenlerinin ortalaması > 0.5 -> 1, < 0.5 -> 0, tam yarı / hiç yok -> NaN."""
    ort = tablo[SUTUNLAR].mean(axis=1)
    return ort.map(lambda o: np.nan if pd.isna(o) or o == 0.5 else float(o > 0.5))


def main():
    tablo = pd.read_pickle(VERI / "oyun_tablosu.pkl").reset_index(drop=True)
    metin = tablo["yorumlar"].map(" ".join)
    hedefler = {"genel_olas": genel_karanlik(tablo),
                "reklam_olas": tablo["t13"],
                "durdurma_olas": tablo["t28"]}

    skor = pd.DataFrame({"oyun_id": tablo["oyun_id"]})
    for ad in hedefler:
        skor[ad] = np.nan

    katlar = KFold(n_splits=5, shuffle=True, random_state=ilk_model.TOHUM)
    for egitim, sinav in katlar.split(tablo):
        tfidf = clone(ilk_model.model_kur()[0])
        X_eg = tfidf.fit_transform(metin.iloc[egitim])
        X_sn = tfidf.transform(metin.iloc[sinav])
        for ad, hedef in hedefler.items():
            y = hedef.iloc[egitim]
            bilinen = y.notna().to_numpy()
            model = LogisticRegression(class_weight="balanced", max_iter=2000)
            model.fit(X_eg[bilinen], y[bilinen].astype(int))
            skor.loc[sinav, ad] = model.predict_proba(X_sn)[:, 1]

    skor["renk"] = skor["genel_olas"].map(renk)
    skor["genel_gercek"] = hedefler["genel_olas"]
    skor["liste"] = tablo["liste"]          # SADECE kontrol için; kartta kullanılmaz
    skor.to_csv(CIKTI, index=False, encoding="utf-8")

    # Kalibrasyon: model X dediğinde gerçekte kaçı karanlık?
    bilinen = skor["genel_gercek"].notna()
    k = skor[bilinen].copy()
    k["dilim"] = pd.cut(k["genel_olas"], bins=[0, .1, .2, .3, .4, .5, .6, .7, .8, .9, 1],
                        include_lowest=True)
    tablo_k = k.groupby("dilim", observed=True).agg(
        oyun=("genel_gercek", "size"),
        model_ortalama=("genel_olas", "mean"),
        gercek_oran=("genel_gercek", "mean"))
    print(f"{len(skor)} oyun puanlandı, {bilinen.sum()} tanesinin genel etiketi belli.\n")
    print("Kalibrasyon (genel risk):")
    print(tablo_k.to_string(float_format="%.2f"))

    # Derecelendirme ölçeği: her rengin geçmişte gerçekleşen 'karanlık' oranı
    olcek = skor.groupby("renk").agg(
        oyun=("oyun_id", "size"),
        gercek_karanlik_orani=("genel_gercek", "mean"),
        tuzakli_listeden=("liste", lambda l: (l == "dark").mean()),
    ).reindex(["yesil", "sari", "kirmizi"])
    print("\nRenk ölçeği:")
    print(olcek.to_string(float_format="%.2f"))

    # İki özel tuzak: model 'var' dediğinde (>= 0.5) gerçekte kaçı var?
    for ad, sutun in (("reklam_olas", "t13"), ("durdurma_olas", "t28")):
        b = tablo[sutun].notna()
        isaret = skor.loc[b, ad] >= 0.5
        gercek = tablo.loc[b, sutun]
        print(f"\n{ad}: uyarı verilen {isaret.sum()} oyun, bunların %{100 * gercek[isaret].mean():.0f}'inde "
              f"tuzak gerçekten var; uyarı verilmeyenlerde %{100 * gercek[~isaret].mean():.0f}")


if __name__ == "__main__":
    main()
