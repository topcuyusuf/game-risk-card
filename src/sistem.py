"""Dondurulmuş sistem: bilinen 485 oyunla eğitilmiş modeller + kurallar -> tek oyun için kart.

Hem oysuz oyunlar (19), hem bağımsız test (23), hem de demo (24) aynı fonksiyonu kullanır;
böylece her yerde birebir aynı kural çalışır.
    sistem = sistemi_yukle()
    kart = kart_uret(sistem, oyun_id, ad, yorumlar, aciklama, magaza)
"""

import importlib
import random
from collections import Counter

import joblib
import pandas as pd

from ortak import VERI

ilk_model = importlib.import_module("10_ilk_model")
risk = importlib.import_module("14_risk_skoru")
kanitlar = importlib.import_module("15_kanitlar")
kart_mod = importlib.import_module("16_kart")
import aile

ONBELLEK = VERI / "model" / "sistem.joblib"
KARARLILIK_TEKRAR = 15      # yeniden örnekleme sayısı (tekrar başına ~0.25 sn)
KARARLILIK_ESIK = kart_mod.KARARLILIK_ESIK   # 0.90; 45. adımda seçildi


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
            "renk_olcegi": pd.read_json(VERI / "renk_olcegi.json", typ="series"),
            "sure_olcegi": kart_mod.sure_olcegi_oku(), "alternatifler": aile.alternatif_oku()}


def sistemi_yukle(yeniden=False):
    """Önbellekte varsa yükler (saniyeler), yoksa eğitip kaydeder (~1 dk)."""
    if ONBELLEK.exists() and not yeniden:
        return joblib.load(ONBELLEK)
    sistem = sistemi_egit()
    ONBELLEK.parent.mkdir(exist_ok=True)
    joblib.dump(sistem, ONBELLEK)
    return sistem


def renk_hesapla(modeller, karne, oyun_id, yorumlar, aciklama="", magaza=None):
    """Yalnızca renk ve puan (kanıt metni, aile kutusu yok); yeniden örnekleme için hafif yol."""
    s = {ad_: float(m.predict_proba([" ".join(y["metin"] for y in yorumlar)])[0, 1]) for ad_, m in modeller.items()}
    s["renk"] = risk.renk(s["genel_olas"])
    k = kart_mod.kart_kur(oyun_id, "", s, kanitlar.oyun_kanitlari(yorumlar, aciklama), karne, magaza)
    return k["renk"], k["puan"]


def kararlilik(modeller, karne, oyun_id, yorumlar, renk, aciklama="", magaza=None, tekrar=KARARLILIK_TEKRAR, tohum=0):
    """Yorumlar yerine koyarak yeniden örneklenir (bootstrap); her örnekte renk yeniden hesaplanır.
    Dönüş: {'oran': aynı renk payı, 'diger': en sık farklı renk ya da None, 'sinirda': oran < eşik}"""
    r = random.Random(tohum)
    renkler = Counter(renk_hesapla(modeller, karne, oyun_id, r.choices(yorumlar, k=len(yorumlar)), aciklama, magaza)[0]
                      for _ in range(tekrar))
    oran = renkler[renk] / tekrar
    diger = max((c for c in renkler if c != renk), key=lambda c: renkler[c], default=None)
    return {"oran": round(oran, 2), "diger": diger, "sinirda": oran < KARARLILIK_ESIK}


def kart_uret(sistem, oyun_id, ad, yorumlar, aciklama="", magaza=None):
    """yorumlar: [{'metin', 'yildiz', 'faydali_oy'}, ...]. Tek oyunun kartını döndürür."""
    yorumlar = [y for y in yorumlar if y.get("metin")]
    tek_metin = [" ".join(y["metin"] for y in yorumlar)]
    s = {ad_: float(m.predict_proba(tek_metin)[0, 1]) for ad_, m in sistem["modeller"].items()}
    s["renk"] = risk.renk(s["genel_olas"])
    kanit_oyun = kanitlar.oyun_kanitlari(kanitlar.yorumlari_sirala(yorumlar), aciklama)
    k = kart_mod.kart_kur(oyun_id, ad, s, kanit_oyun, sistem["karne"], magaza)
    k["renk_aciklama"] = kart_mod.renk_cumlesi(k["renk"], sistem["renk_olcegi"])
    k["sure_aciklama"] = kart_mod.sure_cumlesi(k["renk"], sistem.get("sure_olcegi"))
    k["genel_olas"] = round(s["genel_olas"], 2)
    k["yorum_sayisi"] = len(yorumlar)
    k["kararlilik"] = kararlilik(sistem["modeller"], sistem["karne"], oyun_id, yorumlar, k["renk"], aciklama, magaza)
    aile.ekle(k, magaza, aciklama, sistem.get("alternatifler", {}))   # çocuk bilgisi, ipuçları, alternatifler
    return k
