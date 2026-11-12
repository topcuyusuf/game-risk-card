"""Adım 27: 347 iOS oyununu eğitime eklemek Play'deki tahmini iyileştiriyor mu?

485 Play oyunu 5 parçaya bölünür (3 farklı karıştırmayla tekrarlanır = 15 sınav).
Her sınavda aynı model iki kez eğitilir:
  A) sadece Play eğitim parçaları
  B) Play eğitim parçaları + 347 iOS oyununun tamamı
İkisi de AYNI Play sınav parçasında ölçülür. iOS oyunları hiçbir zaman sınavda yer almaz.
Model ayarları, eşikler, ağırlıklar değişmez.
Kullanım:  python src/27_ios_ekleme_kontrolu.py
"""

import importlib
import json
import sys
from collections import defaultdict

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import RepeatedStratifiedKFold

from ortak import HEDEF_TUZAKLAR, VERI

ilk_model = importlib.import_module("10_ilk_model")
risk = importlib.import_module("14_risk_skoru")
etiket_mod = importlib.import_module("08_etiketler")
test_mod = importlib.import_module("23_bagimsiz_test")


def ios_tablosu():
    """347 iOS oyunu: Play tablosuyla aynı sütunlar (yorum metni + t.. etiketleri)."""
    oy, _ = test_mod.oylar_ve_adaylar()
    yorum = defaultdict(list)
    for s in open(test_mod.YORUMLAR, encoding="utf-8"):
        y = json.loads(s)
        if y.get("metin"):
            yorum[y["oyun_id"]].append(y["metin"])
    satir = []
    for s in open(test_mod.OYUNLAR, encoding="utf-8"):
        i = json.loads(s)["oyun_id"]
        satir.append({"oyun_id": i, "yorumlar": yorum[i],
                      **{f"t{t}": etiket_mod.etiket(*oy[i].get(t, (0, 0))) for t in HEDEF_TUZAKLAR}})
    return pd.DataFrame(satir).astype({f"t{t}": float for t in HEDEF_TUZAKLAR})


def hedefler(tablo):
    h = {"Genel (kart ikinci görüşü)": risk.genel_karanlik(tablo)}
    h.update({HEDEF_TUZAKLAR[t]: tablo[f"t{t}"] for t in HEDEF_TUZAKLAR})
    return h


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    play = pd.read_pickle(VERI / "oyun_tablosu.pkl").reset_index(drop=True)
    ios = ios_tablosu()
    pm, im = play["yorumlar"].map(" ".join), ios["yorumlar"].map(" ".join)
    hp, hi = hedefler(play), hedefler(ios)
    sistem = {"Genel (kart ikinci görüşü)", "Advertisements", "Can't Pause or Save"}

    satirlar = []
    for ad in hp:
        yp, yi = hp[ad], hi[ad]
        bp, bi = yp.notna().to_numpy(), yi.notna().to_numpy()
        Xp, Yp = pm[bp].reset_index(drop=True), yp[bp].astype(int).reset_index(drop=True)
        Xi, Yi = im[bi], yi[bi].astype(int)
        if Yp.sum() < 10 or (len(Yp) - Yp.sum()) < 10:
            continue
        a, b = [], []
        for eg, sv in RepeatedStratifiedKFold(n_splits=5, n_repeats=3, random_state=42).split(Xp, Yp):
            ma = ilk_model.model_kur().fit(Xp[eg], Yp[eg])
            mb = ilk_model.model_kur().fit(pd.concat([Xp[eg], Xi]), pd.concat([Yp[eg], Yi]))
            a.append(roc_auc_score(Yp[sv], ma.predict_proba(Xp[sv])[:, 1]))
            b.append(roc_auc_score(Yp[sv], mb.predict_proba(Xp[sv])[:, 1]))
        a, b = np.array(a), np.array(b)
        satirlar.append({"hedef": ad, "sistemde": ad in sistem, "play_oyun": len(Yp), "ios_ek": len(Yi),
                         "auc_sadece_play": a.mean(), "auc_play_ios": b.mean(), "fark": (b - a).mean(),
                         "iyilesen_sinav": int((b > a).sum())})
        print(f"{ad:<28} {a.mean():.3f} -> {b.mean():.3f}  ({(b - a).mean():+.3f}, {int((b > a).sum())}/15 sınavda daha iyi)", flush=True)

    df = pd.DataFrame(satirlar)
    df.to_csv(VERI / "sonuclar_ios_ekleme.csv", index=False, encoding="utf-8")
    print("\nSistemde kullanılan 3 model:")
    print(df[df.sistemde].to_string(index=False, float_format="%.3f"))
    print(f"\nTüm hedeflerin ortalama farkı: {df.fark.mean():+.3f} | iyileşen hedef: {(df.fark > 0).sum()}/{len(df)}")


if __name__ == "__main__":
    main()
