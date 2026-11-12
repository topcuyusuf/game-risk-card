"""Adım 6: Yeterli oyu olan oyunlar Google Play'de hâlâ yayında mı? Yayındaysa mağaza bilgilerini kaydet.

Sadece şu oyunlara bakar: 14 hedef tuzaktan en az birinde >= 2 oy + Play kimliği var.
Kullanım:  python src/06_play_kontrol.py --adet 5
"""

import argparse
import csv
import json
import time
from collections import defaultdict

from google_play_scraper import app
from google_play_scraper.exceptions import NotFoundError

from ortak import HEDEF_TUZAKLAR, VERI

MIN_OY = 2
BEKLEME_SN = 2
CIKTI = VERI / "play_bilgi.jsonl"   # Her satır bir oyunun bilgisi (JSON).

# Modele girebilecek mağaza bilgileri. Geliştirici adı bilerek YOK (ezberleme riski).
ALANLAR = ["title", "genre", "genreId", "score", "ratings", "reviews", "installs",
           "free", "price", "containsAds", "offersIAP", "inAppProductPrice",
           "contentRating", "released", "lastUpdatedOn", "summary", "description"]


def adaylari_bul():
    """Yeterli oyu ve Play kimliği olan oyunları (oyun_id, play_id) listesi olarak döndürür."""
    yeterli = defaultdict(int)
    with open(VERI / "tuzak_oylari.csv", encoding="utf-8", newline="") as f:
        for s in csv.DictReader(f):
            if int(s["tuzak_id"]) in HEDEF_TUZAKLAR and int(s["var"]) + int(s["yok"]) >= MIN_OY:
                yeterli[s["oyun_id"]] += 1
    with open(VERI / "oyun_durum.csv", encoding="utf-8", newline="") as f:
        return [(s["oyun_id"], s["play_id"]) for s in csv.DictReader(f)
                if s["play_id"] and yeterli[s["oyun_id"]] > 0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--adet", type=int, default=None)
    args = parser.parse_args()

    bitmis = set()
    if CIKTI.exists():
        with open(CIKTI, encoding="utf-8") as f:
            # 'hata' olanlar bitmiş sayılmaz; tekrar çalıştırınca yeniden denenir.
            kayitlar = [json.loads(satir) for satir in f]
            bitmis = {k["oyun_id"] for k in kayitlar if k["durum"] != "hata"}

    adaylar = adaylari_bul()
    yapilacak = [a for a in adaylar if a[0] not in bitmis][: args.adet]
    print(f"{len(adaylar)} aday, {len(bitmis)} bitmiş, şimdi {len(yapilacak)} kontrol edilecek.")

    with open(CIKTI, "a", encoding="utf-8") as f:
        for sira, (oyun_id, play_id) in enumerate(yapilacak, 1):
            kayit = {"oyun_id": oyun_id, "play_id": play_id}
            try:
                bilgi = app(play_id, lang="en", country="us")
                kayit["durum"] = "yayinda"
                kayit.update({alan: bilgi.get(alan) for alan in ALANLAR})
            except NotFoundError:
                kayit["durum"] = "kaldirilmis"
            except Exception as hata:          # Ağ hatası vb. — tekrar denenebilir.
                kayit["durum"] = "hata"
                kayit["hata"] = str(hata)[:200]
            f.write(json.dumps(kayit, ensure_ascii=False) + "\n")
            f.flush()
            print(f"[{sira}/{len(yapilacak)}] {play_id}: {kayit['durum']}"
                  f"{'  - ' + str(kayit.get('title')) if kayit['durum'] == 'yayinda' else ''}")
            time.sleep(BEKLEME_SN)


if __name__ == "__main__":
    main()
