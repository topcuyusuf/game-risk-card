"""Dondurulmuş sistem: bilinen 485 oyunla eğitilmiş modeller + kurallar -> tek oyun için kart.

Hem oysuz oyunlar (19), hem bağımsız test (23), hem de demo (24) aynı fonksiyonu kullanır;
böylece her yerde birebir aynı kural çalışır.
    sistem = sistemi_yukle()
    kart = kart_uret(sistem, oyun_id, ad, yorumlar, aciklama, magaza)
"""

import importlib

import joblib
import pandas as pd

from ortak import VERI

ilk_model = importlib.import_module("10_ilk_model")
risk = importlib.import_module("14_risk_skoru")
kanitlar = importlib.import_module("15_kanitlar")
kart_mod = importlib.import_module("16_kart")

ONBELLEK = VERI / "model" / "sistem.joblib"


def sistemi_egit():
    """Modelleri 485 oyunun HEPSİYLE eğitir; kural karnesini ve renk ölçeğini hazırlar."""
    tablo = pd.read_pickle(VERI / "oyun_tablosu.pkl").reset_index(drop=True)
    metin = tablo["yorumlar"].map(" ".join)
    hedefler = {"genel_olas": risk.genel_karanlik(tablo), "reklam_olas": tablo["t13"],
                "durdurma_olas": tablo["t28"]}
    modeller = {}
    for ad, y in hedefler.items():
        bilinen = y.notna()
        modeller[ad] = ilk_model.model_kur().fit(metin[bilinen], y[bilinen].astype(int))

    t_idx, skor, kanit_eski, _, _ = kart_mod.oku()
    oran = pd.DataFrame({f"t{t}": {o: v[str(t)]["eslesen_yorum"] / max(v[str(t)]["toplam_yorum"], 1)
                                  for o, v in kanit_eski.items()} for t in kart_mod.HEDEF_TUZAKLAR})
    return {"modeller": modeller, "karne": kart_mod.kural_karnesi(t_idx, skor, oran),
            "renk_olcegi": pd.read_json(VERI / "renk_olcegi.json", typ="series")}


def sistemi_yukle(yeniden=False):
    """Önbellekte varsa yükler (saniyeler), yoksa eğitip kaydeder (~1 dk)."""
    if ONBELLEK.exists() and not yeniden:
        return joblib.load(ONBELLEK)
    sistem = sistemi_egit()
    ONBELLEK.parent.mkdir(exist_ok=True)
    joblib.dump(sistem, ONBELLEK)
    return sistem


def kart_uret(sistem, oyun_id, ad, yorumlar, aciklama="", magaza=None):
    """yorumlar: [{'metin', 'yildiz', 'faydali_oy'}, ...]. Tek oyunun kartını döndürür."""
    yorumlar = [y for y in yorumlar if y.get("metin")]
    tek_metin = [" ".join(y["metin"] for y in yorumlar)]
    s = {ad_: float(m.predict_proba(tek_metin)[0, 1]) for ad_, m in sistem["modeller"].items()}
    s["renk"] = risk.renk(s["genel_olas"])
    kanit_oyun = kanitlar.oyun_kanitlari(kanitlar.yorumlari_sirala(yorumlar), aciklama)
    k = kart_mod.kart_kur(oyun_id, ad, s, kanit_oyun, sistem["karne"], magaza)
    k["renk_aciklama"] = kart_mod.renk_cumlesi(k["renk"], sistem["renk_olcegi"])
    k["genel_olas"] = round(s["genel_olas"], 2)
    k["yorum_sayisi"] = len(yorumlar)
    return k
