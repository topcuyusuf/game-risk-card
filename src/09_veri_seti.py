"""Adım 9: Etiket, mağaza bilgisi, açıklama ve yorumları tek bir oyun tablosunda birleştirir.

Her satır = bir oyun. Model bu tabloyu kullanacak.
Kullanım:  python src/09_veri_seti.py
"""

import json
import re

import pandas as pd
from bs4 import BeautifulSoup

from ortak import HEDEF_TUZAKLAR, VERI

CIKTI = VERI / "oyun_tablosu.pkl"
ETIKETLER = [f"t{t}" for t in HEDEF_TUZAKLAR]


def metin_mi(deger):
    """Değer metinse kendisini, değilse (boş/NaN) '' döndürür."""
    return deger if isinstance(deger, str) else ""


def html_temizle(metin):
    """Açıklamadaki <b>, <br> gibi HTML etiketlerini atıp düz metin bırakır."""
    return BeautifulSoup(metin_mi(metin), "html.parser").get_text(" ", strip=True)


def indirme_sayisi(metin):
    """'1,000,000+' -> 1000000"""
    rakamlar = re.sub(r"[^0-9]", "", metin_mi(metin))
    return int(rakamlar) if rakamlar else None


def en_yuksek_fiyat(metin):
    """'$0.99 - $74.99 per item' -> 74.99 (uygulama içi en pahalı ürün; yoksa 0)"""
    fiyatlar = re.findall(r"\d+(?:\.\d+)?", metin_mi(metin).replace(",", ""))
    return max(float(f) for f in fiyatlar) if fiyatlar else 0.0


def main():
    # 1) Etiketler: en az bir kesin etiketi olan oyunlar
    etiket = pd.read_csv(VERI / "etiketler.csv", dtype={"oyun_id": str})
    etiket = etiket[etiket[ETIKETLER].notna().any(axis=1)]

    # 2) Mağaza bilgileri (her oyun için son kayıt)
    kayitlar = [json.loads(s) for s in open(VERI / "play_bilgi.jsonl", encoding="utf-8")]
    magaza = pd.DataFrame(kayitlar).drop_duplicates("oyun_id", keep="last")
    magaza = magaza[magaza["durum"] == "yayinda"]
    magaza = pd.DataFrame({
        "oyun_id": magaza["oyun_id"],
        "tur": magaza["genreId"],
        "play_puani": magaza["score"],
        "puan_veren": magaza["ratings"],
        "indirme": magaza["installs"].map(indirme_sayisi),
        "ucretsiz": magaza["free"].astype(int),
        "fiyat": magaza["price"],
        "reklam_var": magaza["containsAds"].astype(int),
        "satin_alma_var": magaza["offersIAP"].astype(int),
        "max_urun_fiyati": magaza["inAppProductPrice"].map(en_yuksek_fiyat),
        "yas_siniri": magaza["contentRating"],
        # Biçimi açıkça veriyoruz: 'Aug 27, 2019'. Vermezsek pandas ilk satırdan tahmin edip
        # diğerlerini okuyamıyor.
        "cikis_yili": pd.to_datetime(magaza["released"], format="%b %d, %Y",
                                     errors="coerce").dt.year,
        "aciklama": (magaza["summary"].fillna("") + " " +
                     magaza["description"].map(html_temizle)),
    })

    # 3) Yorumlar: her oyunun yorumlarını bir liste olarak tut
    yorumlar = pd.read_json(VERI / "play_yorumlar.jsonl", lines=True, dtype={"oyun_id": str})
    oyun_yorumlari = (yorumlar.groupby("oyun_id")
                      .agg(yorumlar=("metin", list),
                           yorum_sayisi=("metin", "size"),
                           ort_yildiz=("yildiz", "mean"))
                      .reset_index())

    # 4) Hepsini oyun_id üzerinden birleştir (sadece üçünde de olan oyunlar kalır)
    tablo = (etiket.merge(magaza, on="oyun_id", how="inner")
                   .merge(oyun_yorumlari, on="oyun_id", how="inner"))
    tablo.to_pickle(CIKTI)

    print(f"Etiketli oyun: {len(etiket)} | mağaza: {len(magaza)} | yorumlu: {len(oyun_yorumlari)}")
    print(f"Birleşik tablo: {len(tablo)} oyun, {tablo.shape[1]} sütun -> {CIKTI.name}")


if __name__ == "__main__":
    main()
