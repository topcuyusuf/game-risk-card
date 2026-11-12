"""Adım 13: Oyun açıklaması tuzağa özel sinyali artırıyor mu?

Üç metin kaynağını (yorum / açıklama / ikisi) aynı sınav oyunlarında dener.
Her kaynakta 12. adımdaki gibi ÖZEL ve GENEL modeli karşılaştırır.
Kullanım:  python src/13_aciklama_ekle.py
"""

import importlib

import numpy as np
import pandas as pd
from scipy.sparse import hstack
from sklearn.base import clone
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import KFold

from ortak import HEDEF_TUZAKLAR, VERI

ilk_model = importlib.import_module("10_ilk_model")
onceki = importlib.import_module("12_genel_vs_ozel")   # genel_hedef() fonksiyonu için
SUTUNLAR = onceki.SUTUNLAR
KAYNAKLAR = ["yorum", "aciklama", "ikisi"]
CIKTI = VERI / "sonuclar_aciklama.csv"


def yeni_tfidf():
    """10. adımdaki kelime ayarlarının taze bir kopyası."""
    return clone(ilk_model.model_kur()[0])


def ozellikler(metinler, egitim, sinav):
    """Her kaynak için (X_egitim, X_sinav) üretir. Kelime puanları sadece eğitimden öğrenilir."""
    sonuc = {}
    for ad in ("yorum", "aciklama"):
        tfidf = yeni_tfidf()
        sonuc[ad] = (tfidf.fit_transform(metinler[ad].iloc[egitim]),
                     tfidf.transform(metinler[ad].iloc[sinav]))
    # İkisi birlikte: iki kelime tablosunu yan yana koy
    sonuc["ikisi"] = (hstack([sonuc["yorum"][0], sonuc["aciklama"][0]]).tocsr(),
                      hstack([sonuc["yorum"][1], sonuc["aciklama"][1]]).tocsr())
    return sonuc


def main():
    tablo = pd.read_pickle(VERI / "oyun_tablosu.pkl").reset_index(drop=True)
    metinler = {"yorum": tablo["yorumlar"].map(" ".join), "aciklama": tablo["aciklama"]}
    genel = {s: onceki.genel_hedef(tablo, s) for s in SUTUNLAR}

    # tahmin[(kaynak, hedef)] = her oyun x her tuzak için sınav olasılığı
    tahmin = {(k, h): pd.DataFrame(np.nan, index=tablo.index, columns=SUTUNLAR)
              for k in KAYNAKLAR for h in ("ozel", "genel")}

    katlar = KFold(n_splits=5, shuffle=True, random_state=ilk_model.TOHUM)
    for tur, (egitim, sinav) in enumerate(katlar.split(tablo), 1):
        X = ozellikler(metinler, egitim, sinav)
        for k in KAYNAKLAR:
            X_eg, X_sn = X[k]
            for s in SUTUNLAR:
                for h, hedef in (("ozel", tablo[s]), ("genel", genel[s])):
                    y = hedef.iloc[egitim]
                    bilinen = y.notna().to_numpy()
                    model = LogisticRegression(class_weight="balanced", max_iter=2000)
                    model.fit(X_eg[bilinen], y[bilinen].astype(int))
                    tahmin[(k, h)].loc[sinav, s] = model.predict_proba(X_sn)[:, 1]
        print(f"tur {tur}/5 bitti")

    satirlar = []
    for s in SUTUNLAR:
        bilinen = tablo[s].notna()
        y = tablo.loc[bilinen, s].astype(int)
        satir = {"tuzak": HEDEF_TUZAKLAR[int(s[1:])]}
        for k in KAYNAKLAR:
            ozel = roc_auc_score(y, tahmin[(k, "ozel")].loc[bilinen, s])
            gen = roc_auc_score(y, tahmin[(k, "genel")].loc[bilinen, s])
            satir[f"{k}_ozel"] = ozel
            satir[f"{k}_fark"] = ozel - gen
        satirlar.append(satir)

    sonuc = pd.DataFrame(satirlar)
    sonuc.to_csv(CIKTI, index=False, encoding="utf-8")
    pd.set_option("display.width", 200)
    print("\nAUC (özel model) ve 'fark' = özel - genel")
    print(sonuc.to_string(index=False, float_format="%.3f"))
    print("\nOrtalama:", sonuc.drop(columns="tuzak").mean().round(3).to_dict())


if __name__ == "__main__":
    main()
