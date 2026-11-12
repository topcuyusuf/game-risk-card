"""Adım 5: darkpattern.games oyunlarını Google Play'deki uygulamalarla adına göre eşleştirir.

Oyun adı SADECE eşleştirme için kullanılır, modele girdi olarak verilmez.
Kullanım:  python src/05_play_eslestir.py --adet 10
"""

import argparse
import csv
import re
import time
from difflib import SequenceMatcher

from google_play_scraper import search

from ortak import VERI

LINKLER = VERI / "oyun_linkleri.csv"
ESLESME = VERI / "play_eslesme.csv"
BEKLEME_SN = 2          # Google Play'e de nazik olalım.
GUVENLI = 0.85          # Bu benzerliğin üstü: kabul.
KONTROL = 0.60          # Bu ile GUVENLI arası: elle kontrol.
BASLIKLAR = ["oyun_id", "ad", "android", "play_id", "play_ad", "play_gelistirici",
             "play_tur", "benzerlik", "durum"]


def sadelestir(metin):
    """Karşılaştırma için adı sadeleştirir: küçük harf, noktalama yok, 'tm' gibi ekler yok."""
    metin = metin.lower()
    metin = re.sub(r"[™®©]", "", metin)
    metin = re.sub(r"[^a-z0-9 ]", " ", metin)
    return " ".join(metin.split())


def benzerlik(a, b):
    """İki ad arasındaki benzerlik (0 = hiç, 1 = aynı).

    Play adları genelde uzundur ('Ad: Alt başlık'), bu yüzden
    hem tam adı hem de ':' ya da '-' öncesini deneyip yüksek olanı alırız.
    """
    a = sadelestir(a)
    adaylar = [b, re.split(r"[:\-–|]", b)[0]]
    return max(SequenceMatcher(None, a, sadelestir(x)).ratio() for x in adaylar)


def en_iyi_eslesme(ad):
    """Play'de adı arar, en benzer sonucu ve benzerlik puanını döndürür."""
    try:
        sonuclar = search(ad, lang="en", country="us", n_hits=5)
    except Exception as hata:
        print(f"  ! Arama hatası: {hata}")
        return None, 0.0
    sonuclar = [s for s in sonuclar if s.get("appId")]   # Bazen id'siz sonuç geliyor.
    if not sonuclar:
        return None, 0.0
    en_iyi = max(sonuclar, key=lambda s: benzerlik(ad, s["title"]))
    return en_iyi, benzerlik(ad, en_iyi["title"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--adet", type=int, default=None)
    args = parser.parse_args()

    with open(LINKLER, encoding="utf-8", newline="") as f:
        oyunlar = list(csv.DictReader(f))

    bitmis = set()
    if ESLESME.exists():
        with open(ESLESME, encoding="utf-8", newline="") as f:
            bitmis = {s["oyun_id"] for s in csv.DictReader(f)}

    yapilacak = [o for o in oyunlar if o["oyun_id"] not in bitmis][: args.adet]
    yeni = not ESLESME.exists()
    with open(ESLESME, "a", encoding="utf-8", newline="") as f:
        yazici = csv.DictWriter(f, fieldnames=BASLIKLAR)
        if yeni:
            yazici.writeheader()

        for oyun in yapilacak:
            sonuc, puan = en_iyi_eslesme(oyun["ad"])
            durum = "kabul" if puan >= GUVENLI else "kontrol" if puan >= KONTROL else "yok"
            yazici.writerow({
                "oyun_id": oyun["oyun_id"], "ad": oyun["ad"], "android": oyun["android"],
                "play_id": sonuc["appId"] if sonuc else "",
                "play_ad": sonuc["title"] if sonuc else "",
                # Geliştirici sadece elle kontrol için; modele girmeyecek.
                "play_gelistirici": sonuc.get("developer", "") if sonuc else "",
                "play_tur": sonuc.get("genre", "") if sonuc else "",
                "benzerlik": round(puan, 2), "durum": durum,
            })
            f.flush()
            print(f"{durum:>7} {puan:.2f}  {oyun['ad']}  ->  "
                  f"{sonuc['title'] if sonuc else '-'} ({sonuc['appId'] if sonuc else '-'})")
            time.sleep(BEKLEME_SN)


if __name__ == "__main__":
    main()
