"""Adım 47: Reklam kaldırma ürünü kalıbının düzeltilmesi kartı nasıl değiştiriyor?

Hata: 16_kart.py'deki kalıpta kelime sınırı (\b) yerine görünmez backspace karakteri yazılmıştı. Bu yüzden
"Ad Removal", "No-Ads Offer", "Disable Ads" gibi ürünler kaçıyordu. 22. adımda sinyal doğru kalıpla seçilmişti.
Deney: kalıp ESKİ ve YENİ hâliyle; diğer her şey aynı. Geliştirme (485) ve bağımsız test (347 iOS).
Kullanım:  python src/47_reklam_urunu.py
"""

import importlib
import json
import re
import sys

import pandas as pd
from sklearn.metrics import roc_auc_score

from ortak import VERI

km = importlib.import_module("16_kart")
kural = importlib.import_module("18_kural_karti")
t23 = importlib.import_module("23_bagimsiz_test")

ESKI = re.compile(r"remove ads?|no ads?|ad[- ]?free", re.I)
YENI = km.REKLAM_URUNU
RENKLER = ["yesil", "sari", "kirmizi"]


def renk(puan, model_renk):
    r = kural.kural_rengi(puan)
    return "kirmizi" if r == "sari" and model_renk == "kirmizi" else r


def satir(k, m, karanlik, t13):
    """Kartın 13 dışındaki kanıtları sabit; mağaza reklam kanıtı iki kalıpla yeniden hesaplanır."""
    magaza_disi = {d["tuzak_id"] for d in k["tespitler"]} | {kural.AD_ID[u["tuzak"]] for u in k["uyarilar"]}
    diger_magaza = {x["tuzak_id"] for x in k.get("magaza_kanit", []) if x["tuzak_id"] != 13}
    temel = {t for t in magaza_disi | diger_magaza if t in kural.AGIRLIK}
    urunler = [u["ad"] for u in (m or {}).get("urunler", [])]
    sonuc = {"oyun_id": k["oyun_id"], "ad": k["ad"], "model_renk": k["model_renk"], "karanlik": karanlik, "t13": t13}
    for s, kalip in (("eski", ESKI), ("yeni", YENI)):
        sinyal = not k.get("reklamsiz") and any(kalip.search(a) for a in urunler)
        ids = temel | ({13} if sinyal else set())
        sonuc[f"sinyal_{s}"] = sinyal
        sonuc[f"puan_{s}"] = sum(kural.AGIRLIK[t] for t in ids)
        sonuc[f"renk_{s}"] = renk(sonuc[f"puan_{s}"], k["model_renk"])
    return sonuc


def rapor(ad, d):
    b = d[d.karanlik.notna()]
    print(f"\n{ad}: {len(d)} kart, karanlık etiketi belli {len(b)}")
    for s in ("eski", "yeni"):
        pay = " / ".join(f"{c} {int((b[f'renk_{s}'] == c).sum())} (%{100 * b.karanlik[b[f'renk_{s}'] == c].mean():.0f})"
                         for c in RENKLER)
        e = d[d.t13.notna() & d[f"sinyal_{s}"]]
        print(f"  {s}: puan AUC {roc_auc_score(b.karanlik, b[f'puan_{s}']):.4f} | {pay} | reklam ürünü sinyali "
              f"{int(d[f'sinyal_{s}'].sum())} oyun, oyla reklam tuzağı %{100 * e.t13.mean():.0f} ({len(e)} oylu)")
    yeni = d[d.sinyal_yeni & ~d.sinyal_eski]
    print(f"  sinyali yeni gelen {len(yeni)} oyun; puanı değişen {int((yeni.puan_eski != yeni.puan_yeni).sum())}")
    print(f"  bu oyunlarda oyla reklam tuzağı: {int((yeni.t13 == 1).sum())} var / {int((yeni.t13 == 0).sum())} yok / "
          f"{int(yeni.t13.isna().sum())} bilinmiyor")
    deg = d[d.renk_eski != d.renk_yeni]
    print(f"  rengi değişen: {len(deg)}")
    for _, r in deg.iterrows():
        print(f"    {r['ad']}: {r.renk_eski} -> {r.renk_yeni} (puan {r.puan_eski} -> {r.puan_yeni}, karanlık {r.karanlik})")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    _, skor, _, _, magaza = km.oku()
    tablo = pd.read_pickle(VERI / "oyun_tablosu.pkl").set_index("oyun_id")
    kartlar = [json.loads(s) for s in open(VERI / "kartlar.jsonl", encoding="utf-8")]
    gel = pd.DataFrame([satir(k, magaza.get(k["oyun_id"]), skor.at[k["oyun_id"], "genel_gercek"],
                              tablo.at[k["oyun_id"], "t13"]) for k in kartlar])
    rapor("GELİŞTİRME", gel)

    sonuc = pd.read_csv(t23.KLASOR / "sonuclar.csv", dtype={"oyun_id": str}).set_index("oyun_id")
    om = {o["oyun_id"]: o["magaza"] for o in map(json.loads, open(t23.KLASOR / "oyunlar.jsonl", encoding="utf-8"))}
    tk = {k["oyun_id"]: k for k in map(json.loads, open(t23.KLASOR / "kartlar.jsonl", encoding="utf-8"))}
    test = pd.DataFrame([satir(tk[o], om.get(o), r.karanlik, r.t13) for o, r in sonuc.iterrows()])
    rapor("BAĞIMSIZ TEST (iOS)", test)
    pd.concat([gel.assign(kume="gelistirme"), test.assign(kume="test")]).to_csv(
        VERI / "sonuclar_reklam_urunu.csv", index=False, encoding="utf-8")


if __name__ == "__main__":
    main()
