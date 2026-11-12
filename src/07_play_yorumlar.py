"""Adım 7: Play'de yayında olan oyunlar için ~200 İngilizce yorum toplar.

Kullanıcı adı ve profil fotoğrafı KAYDEDİLMEZ (kişisel veri, modele faydası yok).
Kullanım:  python src/07_play_yorumlar.py --adet 3
"""

import argparse
import csv
import json
import time

from google_play_scraper import Sort, reviews

from ortak import VERI

BILGI = VERI / "play_bilgi.jsonl"
YORUMLAR = VERI / "play_yorumlar.jsonl"   # Her satır bir yorum.
DURUM = VERI / "yorum_durum.csv"          # Her satır bir oyun: kaç yorum geldi?
HEDEF_YORUM = 200
BEKLEME_SN = 2


def adaylari_oku():
    """Play'de yayında olan ve türü oyun (GAME_...) olan kayıtları döndürür."""
    adaylar = {}
    with open(BILGI, encoding="utf-8") as f:
        for satir in f:
            k = json.loads(satir)
            if k["durum"] == "yayinda" and str(k.get("genreId", "")).startswith("GAME"):
                adaylar[k["oyun_id"]] = k["play_id"]   # Aynı oyun iki kez varsa sonuncusu.
    return list(adaylar.items())


def yorumlari_cek(play_id):
    """Bir oyunun en alakalı İngilizce yorumlarını çeker (en fazla HEDEF_YORUM)."""
    sonuc, _ = reviews(play_id, lang="en", country="us",
                       sort=Sort.MOST_RELEVANT, count=HEDEF_YORUM)
    return sonuc


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--adet", type=int, default=None)
    args = parser.parse_args()

    bitmis = set()
    if DURUM.exists():
        with open(DURUM, encoding="utf-8", newline="") as f:
            bitmis = {s["oyun_id"] for s in csv.DictReader(f) if s["durum"] == "tamam"}

    adaylar = adaylari_oku()
    yapilacak = [a for a in adaylar if a[0] not in bitmis][: args.adet]
    print(f"{len(adaylar)} oyun, {len(bitmis)} bitmiş, şimdi {len(yapilacak)} oyun.")

    yeni = not DURUM.exists()
    with open(YORUMLAR, "a", encoding="utf-8") as f_y, \
         open(DURUM, "a", encoding="utf-8", newline="") as f_d:
        durum_yaz = csv.writer(f_d)
        if yeni:
            durum_yaz.writerow(["oyun_id", "play_id", "durum", "yorum_sayisi"])

        for sira, (oyun_id, play_id) in enumerate(yapilacak, 1):
            try:
                gelen = yorumlari_cek(play_id)
            except Exception as hata:       # Geçici hata: sonra tekrar denenir.
                print(f"[{sira}] {play_id}: HATA {str(hata)[:100]}")
                durum_yaz.writerow([oyun_id, play_id, "hata", 0])
                f_d.flush()
                time.sleep(BEKLEME_SN * 3)
                continue

            for y in gelen:
                f_y.write(json.dumps({
                    "oyun_id": oyun_id,
                    "play_id": play_id,
                    "yorum_id": y["reviewId"],
                    "metin": y["content"],
                    "yildiz": y["score"],
                    "faydali_oy": y["thumbsUpCount"],
                    "tarih": y["at"].isoformat() if y.get("at") else None,
                    "surum": y.get("reviewCreatedVersion"),
                }, ensure_ascii=False) + "\n")
            durum_yaz.writerow([oyun_id, play_id, "tamam", len(gelen)])
            f_y.flush()
            f_d.flush()
            print(f"[{sira}/{len(yapilacak)}] {play_id}: {len(gelen)} yorum")
            time.sleep(BEKLEME_SN)


if __name__ == "__main__":
    main()
