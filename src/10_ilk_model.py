"""Adım 10: Tek bir tuzak için ilk model (yorumlar -> TF-IDF -> lojistik regresyon).

Üç yaklaşımı aynı adil sınavla (5 katlı çapraz doğrulama) karşılaştırır:
  1) Hep çoğunluk sınıfını söyle   (hiç model yok)
  2) Sadece Play'deki tek bir işaret (örn. 'reklam içerir')
  3) Yorumlardan öğrenen model
Kullanım:  python src/10_ilk_model.py --tuzak 13
"""

import argparse

import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import make_pipeline

from ortak import HEDEF_TUZAKLAR, VERI

TOHUM = 42
# Bazı tuzaklar için Play'de doğrudan karşılığı olan bir işaret var.
PLAY_ISARETI = {13: "reklam_var"}


def sonuc_yaz(ad, y, tahmin):
    """Dört ölçüyü tek satırda yazar."""
    print(f"  {ad:<34}"
          f"doğruluk {accuracy_score(y, tahmin):.2f} | "
          f"isabet {precision_score(y, tahmin, zero_division=0):.2f} | "
          f"yakalama {recall_score(y, tahmin):.2f} | "
          f"F1 {f1_score(y, tahmin):.2f}")


def model_kur():
    """Metni sayıya çeviren adım + lojistik regresyon, tek boru hattında."""
    return make_pipeline(
        TfidfVectorizer(
            lowercase=True,
            ngram_range=(1, 2),      # Tek kelime + ikili kelime ("no ads", "watch ad")
            min_df=5,                # En az 5 oyunda geçmeyen kelimeyi at (gürültü)
            max_df=0.9,              # Oyunların %90'ında geçen kelimeyi at (ayırt etmez)
            sublinear_tf=True,       # 100 kez geçmek 10 katı değil, biraz daha önemli olsun
            max_features=30000,
        ),
        LogisticRegression(
            class_weight="balanced",  # Az olan sınıfa ('var') daha çok önem ver
            max_iter=2000,
        ),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tuzak", type=int, default=13)
    args = parser.parse_args()
    sutun = f"t{args.tuzak}"

    tablo = pd.read_pickle(VERI / "oyun_tablosu.pkl")
    veri = tablo[tablo[sutun].notna()].reset_index(drop=True)   # Bilinmeyenler sınava girmez
    y = veri[sutun].astype(int).to_numpy()
    metin = veri["yorumlar"].map(" ".join)                      # 200 yorum -> tek metin

    print(f"Tuzak: {HEDEF_TUZAKLAR[args.tuzak]}  |  {len(veri)} oyun "
          f"({y.sum()} var, {len(y) - y.sum()} yok)\n")

    katlar = StratifiedKFold(n_splits=5, shuffle=True, random_state=TOHUM)

    # 1) Hep çoğunluk
    cogunluk = cross_val_predict(DummyClassifier(strategy="most_frequent"), metin, y, cv=katlar)
    sonuc_yaz("1) Hep 'yok' de (model yok)", y, cogunluk)

    # 2) Play işareti
    if args.tuzak in PLAY_ISARETI:
        isaret = veri[PLAY_ISARETI[args.tuzak]].to_numpy()
        sonuc_yaz(f"2) Sadece Play '{PLAY_ISARETI[args.tuzak]}'", y, isaret)

    # 3) Yorum modeli
    model = model_kur()
    olasilik = cross_val_predict(model, metin, y, cv=katlar, method="predict_proba")[:, 1]
    tahmin = (olasilik >= 0.5).astype(int)
    sonuc_yaz("3) Yorum modeli (TF-IDF + LR)", y, tahmin)

    # Hangi kelimeler etkili? (Yorum için tüm veriyle bir kez eğit)
    model.fit(metin, y)
    kelimeler = model[0].get_feature_names_out()
    agirlik = model[1].coef_[0]
    sira = np.argsort(agirlik)
    print("\n  'Tuzak VAR' yönüne iten kelimeler:", ", ".join(kelimeler[sira[-15:][::-1]]))
    print("  'Tuzak YOK' yönüne iten kelimeler:", ", ".join(kelimeler[sira[:15]]))

    # En emin yanlışlar: incelemek için
    veri["olasilik"] = olasilik
    veri["hata"] = tahmin != y
    yanlis = veri[veri["hata"]].assign(emin=lambda d: (d["olasilik"] - 0.5).abs())
    print("\n  En emin olunan 5 yanlış (oyun_id, gerçek, model olasılığı):")
    for _, s in yanlis.nlargest(5, "emin").iterrows():
        print(f"    {s['oyun_id']:>6}  gerçek={int(s[sutun])}  olasılık={s['olasilik']:.2f}")


if __name__ == "__main__":
    main()
