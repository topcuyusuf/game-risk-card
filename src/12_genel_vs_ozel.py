"""Adım 12: Tuzağa özel model, genel 'karanlık oyun' modelinden daha mı iyi?

Her tuzak X için aynı sınav oyunlarında iki modeli karşılaştırır:
  ÖZEL : X'in kendi etiketleriyle eğitilir.
  GENEL: X HARİÇ diğer 13 etiketin çoğunluğuyla ('genel karanlık') eğitilir.
İkisinin de X'i ne kadar iyi sıraladığına (AUC) bakılır.
Kullanım:  python src/12_genel_vs_ozel.py
"""

import importlib

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import KFold

from ortak import HEDEF_TUZAKLAR, VERI

ilk_model = importlib.import_module("10_ilk_model")
SUTUNLAR = [f"t{t}" for t in HEDEF_TUZAKLAR]
CIKTI = VERI / "sonuclar_genel_vs_ozel.csv"


def genel_hedef(tablo, haric):
    """'haric' tuzak dışındaki bilinen etiketlerin ortalaması > 0.5 ise 1, < 0.5 ise 0.

    Hiç bilinen etiketi olmayan ya da tam yarı yarıya olan oyun: bilinmiyor (NaN).
    """
    ort = tablo[[s for s in SUTUNLAR if s != haric]].mean(axis=1)   # NaN'ler atlanır
    return ort.map(lambda o: np.nan if pd.isna(o) or o == 0.5 else float(o > 0.5))


def main():
    tablo = pd.read_pickle(VERI / "oyun_tablosu.pkl").reset_index(drop=True)
    metin = tablo["yorumlar"].map(" ".join)

    # Her oyun için her tuzakta iki tahmin tutacağız (sınavda olduğu turda dolacak).
    ozel_olas = pd.DataFrame(np.nan, index=tablo.index, columns=SUTUNLAR)
    genel_olas = ozel_olas.copy()

    katlar = KFold(n_splits=5, shuffle=True, random_state=ilk_model.TOHUM)
    for tur, (egitim, sinav) in enumerate(katlar.split(tablo), 1):
        # Kelime puanlarını SADECE eğitim oyunlarıyla öğren, sınav oyunlarına uygula.
        tfidf = clone(ilk_model.model_kur()[0])
        X_egitim = tfidf.fit_transform(metin.iloc[egitim])
        X_sinav = tfidf.transform(metin.iloc[sinav])

        for s in SUTUNLAR:
            for hedef, hedef_tablo in (("ozel", tablo[s]), ("genel", genel_hedef(tablo, s))):
                y = hedef_tablo.iloc[egitim]
                bilinen = y.notna().to_numpy()
                model = LogisticRegression(class_weight="balanced", max_iter=2000)
                model.fit(X_egitim[bilinen], y[bilinen].astype(int))
                olas = model.predict_proba(X_sinav)[:, 1]
                (ozel_olas if hedef == "ozel" else genel_olas).loc[sinav, s] = olas
        print(f"tur {tur}/5 bitti")

    # Değerlendirme: her tuzakta, o tuzağın GERÇEK etiketine göre AUC
    satirlar = []
    for s in SUTUNLAR:
        bilinen = tablo[s].notna()
        y = tablo.loc[bilinen, s].astype(int)
        a_ozel = roc_auc_score(y, ozel_olas.loc[bilinen, s])
        a_genel = roc_auc_score(y, genel_olas.loc[bilinen, s])
        satirlar.append({"tuzak": HEDEF_TUZAKLAR[int(s[1:])], "AUC_ozel": a_ozel,
                         "AUC_genel": a_genel, "fark": a_ozel - a_genel})

    sonuc = pd.DataFrame(satirlar).sort_values("fark", ascending=False)
    sonuc.to_csv(CIKTI, index=False, encoding="utf-8")
    print()
    print(sonuc.to_string(index=False, float_format="%.3f"))


if __name__ == "__main__":
    main()
