"""Adım 11: 10. adımdaki yorum modelini 14 tuzağın hepsinde aynı adil sınavla dener.

Her tuzak için: kaç oyun var, 'hep var de' F1'i, modelin F1 / isabet / yakalama / AUC değeri
ve modeli 'var' yönüne iten ilk 6 kelime.
Kullanım:  python src/11_tum_tuzaklar.py
"""

import importlib

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict

from ortak import HEDEF_TUZAKLAR, VERI

# 10. adımdaki modeli aynen kullanıyoruz (dosya adı rakamla başladığı için importlib).
ilk_model = importlib.import_module("10_ilk_model")
CIKTI = VERI / "sonuclar_tuzak.csv"


def main():
    tablo = pd.read_pickle(VERI / "oyun_tablosu.pkl")
    tablo["metin"] = tablo["yorumlar"].map(" ".join)
    katlar = StratifiedKFold(n_splits=5, shuffle=True, random_state=ilk_model.TOHUM)

    satirlar = []
    for tuzak_id, ad in HEDEF_TUZAKLAR.items():
        veri = tablo[tablo[f"t{tuzak_id}"].notna()]
        y = veri[f"t{tuzak_id}"].astype(int).to_numpy()

        # Kıyas: her oyuna 'var' de
        hep_var_f1 = f1_score(y, np.ones_like(y))

        # Model: görmediği oyunlar için olasılık
        model = ilk_model.model_kur()
        olasilik = cross_val_predict(model, veri["metin"], y, cv=katlar,
                                     method="predict_proba")[:, 1]
        tahmin = (olasilik >= 0.5).astype(int)

        # Yorum için: tüm veriyle bir kez eğit, 'var' yönüne iten kelimeler
        model.fit(veri["metin"], y)
        kelimeler = model[0].get_feature_names_out()
        en_iyi = kelimeler[np.argsort(model[1].coef_[0])[-6:][::-1]]

        satirlar.append({
            "tuzak": ad, "oyun": len(y), "var": int(y.sum()),
            "hep_var_F1": hep_var_f1,
            "F1": f1_score(y, tahmin), "isabet": precision_score(y, tahmin),
            "yakalama": recall_score(y, tahmin), "AUC": roc_auc_score(y, olasilik),
            "kelimeler": ", ".join(en_iyi),
        })
        print(f"bitti: {ad}")

    sonuc = pd.DataFrame(satirlar)
    sonuc["fark"] = sonuc["F1"] - sonuc["hep_var_F1"]   # Model kıyası ne kadar geçti?
    sonuc.to_csv(CIKTI, index=False, encoding="utf-8")

    pd.set_option("display.width", 200)
    print()
    print(sonuc.drop(columns="kelimeler").sort_values("AUC", ascending=False)
          .to_string(index=False, float_format="%.2f"))
    print()
    for _, s in sonuc.sort_values("AUC", ascending=False).iterrows():
        print(f"{s['tuzak']:<28} {s['kelimeler']}")


if __name__ == "__main__":
    main()
