"""Adım 31: 485 geliştirme oyunu için 400 İngilizce Play yorumu (yorum sayısı deneyi).

7. adımla aynı ayarlar (ABD mağazası, İngilizce, 'en alakalı' sıralama), sadece 200 yerine 400 yorum.
Yalnızca Google Play'e istek atılır; darkpattern.games'e gidilmez. Kaldığı yerden devam eder.
Kullanıcı adı ve profil fotoğrafı KAYDEDİLMEZ.
Kullanım:  python src/31_play_yorum_400.py [--adet N]
"""

import argparse
import csv
import json
import sys
import time

import pandas as pd
from google_play_scraper import Sort, reviews

from ortak import VERI

KLASOR = VERI / "yorum_400"
YORUMLAR = KLASOR / "yorumlar.jsonl"
DURUM = KLASOR / "durum.csv"
HEDEF, BEKLEME_SN = 400, 2


def adaylar():
    """Geliştirme tablosundaki 485 oyun ve Play kimlikleri."""
    tablo = pd.read_pickle(VERI / "oyun_tablosu.pkl")
    with open(VERI / "oyun_durum.csv", encoding="utf-8", newline="") as f:
        play = {s["oyun_id"]: s["play_id"] for s in csv.DictReader(f)}
    return [(i, play[i]) for i in tablo["oyun_id"].astype(str) if play.get(i)]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser()
    p.add_argument("--adet", type=int, default=None)
    a = p.parse_args()
    KLASOR.mkdir(exist_ok=True)
    bitmis = set()
    if DURUM.exists():
        with open(DURUM, encoding="utf-8", newline="") as f:
            bitmis = {s["oyun_id"] for s in csv.DictReader(f) if s["durum"] == "tamam"}
    tum = adaylar()
    yapilacak = [x for x in tum if x[0] not in bitmis][: a.adet]
    print(f"{len(tum)} oyun, {len(bitmis)} bitmiş, şimdi {len(yapilacak)}", flush=True)
    yeni = not DURUM.exists()
    with open(YORUMLAR, "a", encoding="utf-8") as f_y, open(DURUM, "a", encoding="utf-8", newline="") as f_d:
        yaz = csv.writer(f_d)
        if yeni:
            yaz.writerow(["oyun_id", "play_id", "durum", "yorum_sayisi"])
        for sira, (oyun_id, play_id) in enumerate(yapilacak, 1):
            try:
                gelen, _ = reviews(play_id, lang="en", country="us", sort=Sort.MOST_RELEVANT, count=HEDEF)
            except Exception as hata:                    # geçici hata: sonraki çalıştırmada tekrar denenir
                print(f"[{sira}] {play_id}: HATA {str(hata)[:100]}", flush=True)
                yaz.writerow([oyun_id, play_id, "hata", 0]); f_d.flush()
                time.sleep(BEKLEME_SN * 3)
                continue
            for sira_no, y in enumerate(gelen):          # sira_no: Play'in 'en alakalı' sırası (0 = ilk)
                f_y.write(json.dumps({"oyun_id": oyun_id, "sira": sira_no, "metin": y["content"],
                                      "yildiz": y["score"], "faydali_oy": y["thumbsUpCount"]},
                                     ensure_ascii=False) + "\n")
            yaz.writerow([oyun_id, play_id, "tamam", len(gelen)])
            f_y.flush(); f_d.flush()
            if sira % 25 == 0:
                print(f"[{sira}/{len(yapilacak)}] {play_id}: {len(gelen)} yorum", flush=True)
            time.sleep(BEKLEME_SN)


if __name__ == "__main__":
    main()
