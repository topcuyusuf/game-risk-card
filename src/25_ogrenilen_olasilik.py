"""Adım 25: Var/yok eşiği yerine, sinyallerden ÖĞRENİLEN tuzak olasılığı.

Her tuzak için küçük bir lojistik regresyon:
  girdiler : yorumlarda konuşulma oranı (karekök), mağaza sinyali (varsa), özel model olasılığı (reklam/durdurma)
  çıktı    : P(tuzak var)
Kart puanı (olasılıklı) = Σ ağırlık × P(tuzak).  Ağırlıklar (3/2/1) elle verilen değer yargısı olarak kalır.

Geliştirme verisinde 5 katlı sınavla, varsa bağımsız iOS test setinde dondurulmuş haliyle ölçülür.
Kullanım:  python src/25_ogrenilen_olasilik.py          (sadece geliştirme verisi)
           python src/25_ogrenilen_olasilik.py --test   (bağımsız test dahil; toplama bitince)
"""

import importlib
import json
from collections import defaultdict

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import KFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import sistem as sistem_mod
from ortak import HEDEF_TUZAKLAR, VERI

kanit_mod = importlib.import_module("15_kanitlar")
kart_mod = importlib.import_module("16_kart")
kural = importlib.import_module("18_kural_karti")
test_mod = importlib.import_module("23_bagimsiz_test")
etiket_mod = importlib.import_module("08_etiketler")

TUZAKLAR = list(kural.AGIRLIK)                       # ağırlığı olan 10 tuzak
MODEL_SUTUN = {13: "reklam_olas", 28: "durdurma_olas"}
MAGAZA_TUZAK = {49, 54, 13}


def ozellikler(oranlar, magaza_ids, model_olas, t):
    """Bir tuzak için özellik tablosu (satır = oyun)."""
    X = pd.DataFrame({"konusulma": np.sqrt(oranlar[t])})
    if t in MAGAZA_TUZAK:
        X["magaza"] = magaza_ids[t].astype(float)
    if t in MODEL_SUTUN:
        X["model"] = model_olas[MODEL_SUTUN[t]]
    return X


def yeni_model():
    return make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))


def olc(ad, puan, karanlik, agirlikli):
    b, g = karanlik.notna(), agirlikli.notna()
    print(f"  {ad:<34} AUC (karanlık) {roc_auc_score(karanlik[b].astype(int), puan[b]):.3f} | "
          f"sıra ilişkisi (ağırlıklı risk) {spearmanr(puan[g], agirlikli[g])[0]:.3f}")


def gelistirme_verisi():
    tablo = pd.read_pickle(VERI / "oyun_tablosu.pkl").set_index("oyun_id")
    _, skor, kanit, _, magaza = kart_mod.oku()
    idx = tablo.index
    oranlar = {t: pd.Series({o: kanit[o][str(t)]["eslesen_yorum"] / max(kanit[o][str(t)]["toplam_yorum"], 1)
                             for o in idx}) for t in TUZAKLAR}
    mk = {o: {m["tuzak_id"] for m in kart_mod.magaza_kanitlari(magaza.get(o))} for o in idx}
    magaza_ids = {t: pd.Series({o: t in mk[o] for o in idx}) for t in MAGAZA_TUZAK}
    etiket = {t: tablo[f"t{t}"] for t in TUZAKLAR}
    puan = pd.read_csv(VERI / "kural_puanlari.csv", dtype={"oyun_id": str}).set_index("oyun_id").loc[idx]
    return idx, oranlar, magaza_ids, skor.loc[idx], etiket, puan


def test_verisi(sistem):
    oy, _ = test_mod.oylar_ve_adaylar()
    oyunlar = [json.loads(s) for s in open(test_mod.OYUNLAR, encoding="utf-8")]
    yorum = defaultdict(list)
    for s in open(test_mod.YORUMLAR, encoding="utf-8"):
        y = json.loads(s)
        yorum[y["oyun_id"]].append(y)
    idx = [o["oyun_id"] for o in oyunlar]
    oranlar = {t: {} for t in TUZAKLAR}
    olas = {c: {} for c in MODEL_SUTUN.values()}
    mk, ikili, et = {}, {}, {}
    for o in oyunlar:
        i, ys = o["oyun_id"], [y for y in yorum[o["oyun_id"]] if y.get("metin")]
        kn = kanit_mod.oyun_kanitlari(kanit_mod.yorumlari_sirala(ys), o["aciklama"])
        for t in TUZAKLAR:
            oranlar[t][i] = kn[str(t)]["eslesen_yorum"] / max(kn[str(t)]["toplam_yorum"], 1)
        metin = [" ".join(y["metin"] for y in ys)]
        for c in olas:
            olas[c][i] = float(sistem["modeller"][c].predict_proba(metin)[0, 1])
        mk[i] = {m["tuzak_id"] for m in kart_mod.magaza_kanitlari(o["magaza"])}
        k = sistem_mod.kart_uret(sistem, i, o["ad"], ys, o["aciklama"], o["magaza"])
        ikili[i] = k["puan"]
        et[i] = {t: etiket_mod.etiket(*oy[i].get(t, (0, 0))) for t in HEDEF_TUZAKLAR}
    oranlar = {t: pd.Series(v) for t, v in oranlar.items()}
    magaza_ids = {t: pd.Series({i: t in mk[i] for i in idx}) for t in MAGAZA_TUZAK}
    etiket = {t: pd.Series({i: et[i][t] for i in idx}, dtype=float) for t in TUZAKLAR}
    tum = pd.DataFrame(et).T.astype(float)
    ort = tum.mean(axis=1)
    karanlik = ort.map(lambda o: np.nan if pd.isna(o) or o == 0.5 else float(o > 0.5))
    agir = pd.Series(kural.AGIRLIK)
    agirlikli = (tum[agir.index] * agir).sum(axis=1) / (tum[agir.index].notna() * agir).sum(axis=1)
    return idx, oranlar, magaza_ids, pd.DataFrame(olas), etiket, pd.Series(ikili), karanlik, agirlikli


def main(test=False):
    idx, oranlar, magaza_ids, skor, etiket, puan = gelistirme_verisi()

    # --- Geliştirme verisi: 5 katlı sınavla öğrenilen olasılık ---
    P = pd.DataFrame(np.nan, index=idx, columns=TUZAKLAR)
    print("GELİŞTİRME VERİSİ (485 oyun, 5 kat)")
    print(f"  {'Tuzak':<28}{'AUC: sadece konuşulma':>22}{'AUC: öğrenilen':>16}")
    katlar = KFold(5, shuffle=True, random_state=42)
    for t in TUZAKLAR:
        X = ozellikler(oranlar, magaza_ids, skor, t)
        y = etiket[t]
        for egitim, sinav in katlar.split(X):
            eg = X.index[egitim][y.iloc[egitim].notna().to_numpy()]
            m = yeni_model().fit(X.loc[eg], y[eg].astype(int))
            P.loc[X.index[sinav], t] = m.predict_proba(X.iloc[sinav])[:, 1]
        b = y.notna()
        print(f"  {HEDEF_TUZAKLAR[t]:<28}{roc_auc_score(y[b].astype(int), oranlar[t][b]):>22.3f}"
              f"{roc_auc_score(y[b].astype(int), P.loc[b, t]):>16.3f}")
    olasilikli = (P * pd.Series(kural.AGIRLIK)).sum(axis=1)
    print("\n  Kart puanı karşılaştırması:")
    olc("Var/yok puanı (şimdiki kart)", puan["puan"], puan["karanlik"], puan["gercek_agirlikli"])
    olc("Olasılıklı puan (öğrenilen)", olasilikli, puan["karanlik"], puan["gercek_agirlikli"])
    olc("Genel model (ikinci görüş)", skor["genel_olas"], puan["karanlik"], puan["gercek_agirlikli"])

    # --- Son modeller: tüm geliştirme verisiyle; öğrenilen katsayılar ---
    modeller = {}
    print("\nÖğrenilen katsayılar (standartlaştırılmış; büyük = daha etkili):")
    for t in TUZAKLAR:
        X = ozellikler(oranlar, magaza_ids, skor, t)
        b = etiket[t].notna()
        modeller[t] = yeni_model().fit(X[b], etiket[t][b].astype(int))
        k = dict(zip(X.columns, modeller[t][-1].coef_[0].round(2)))
        print(f"  {HEDEF_TUZAKLAR[t]:<28}{k}")

    # --- Bağımsız test (varsa): hiçbir şey yeniden ayarlanmaz ---
    if not test:
        print("\nBağımsız test atlandı (--test ile çalıştır; toplama bitmeden bakılmaz).")
        return
    sistem = sistem_mod.sistemi_yukle()
    tidx, toran, tmag, tolas, tetiket, tikili, tkar, tagir = test_verisi(sistem)
    Pt = pd.DataFrame({t: modeller[t].predict_proba(ozellikler(toran, tmag, tolas, t))[:, 1] for t in TUZAKLAR},
                      index=tidx)
    print(f"\nBAĞIMSIZ TEST ({len(tidx)} iOS oyunu; modeller dondurulmuş)")
    print(f"  {'Tuzak':<28}{'AUC: sadece konuşulma':>22}{'AUC: öğrenilen':>16}")
    for t in TUZAKLAR:
        y = tetiket[t]
        b = y.notna()
        if y[b].nunique() < 2:
            continue
        print(f"  {HEDEF_TUZAKLAR[t]:<28}{roc_auc_score(y[b].astype(int), toran[t][b]):>22.3f}"
              f"{roc_auc_score(y[b].astype(int), Pt.loc[b, t]):>16.3f}")
    tolasilikli = (Pt * pd.Series(kural.AGIRLIK)).sum(axis=1)
    genel = pd.Series({i: float(sistem["modeller"]["genel_olas"].predict_proba(
        [" ".join(y["metin"] for y in ys)])[0, 1]) for i, ys in _test_yorumlari().items()}).loc[tidx]
    print("\n  Kart puanı karşılaştırması:")
    olc("Var/yok puanı (şimdiki kart)", tikili, tkar, tagir)
    olc("Olasılıklı puan (öğrenilen)", tolasilikli, tkar, tagir)
    olc("Genel model (ikinci görüş)", genel, tkar, tagir)
    Pt.assign(olasilikli_puan=tolasilikli).to_csv(test_mod.KLASOR / "olasilikli.csv", encoding="utf-8")


def _test_yorumlari():
    yorum = defaultdict(list)
    for s in open(test_mod.YORUMLAR, encoding="utf-8"):
        y = json.loads(s)
        if y.get("metin"):
            yorum[y["oyun_id"]].append(y)
    return yorum


if __name__ == "__main__":
    import sys
    main(test="--test" in sys.argv)
