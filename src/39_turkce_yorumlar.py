"""Adım 39: Aynı 485 oyun için ~200 TÜRKÇE Google Play yorumu toplar (lang=tr, country=tr).

Amaç: kart Türkçe yorumlarla da çalışır mı? Etiketler oyun düzeyinde ve dilden bağımsız (darkpattern.games oyları),
bu yüzden Türkçe yorumlarla aynı etiketlere karşı model eğitilip sınanabilir (40. adım).
Yalnızca Google Play'e istek atılır (2 sn arayla). Kullanıcı adı/fotoğraf kaydedilmez. Kaldığı yerden devam eder.
Çıktı: data/turkce/yorumlar.jsonl, data/turkce/durum.csv
Kullanım:  python src/39_turkce_yorumlar.py
"""

import csv
import importlib
import json
import sys
import time

from google_play_scraper import Sort, reviews

from ortak import VERI

y07 = importlib.import_module("07_play_yorumlar")      # adaylari_oku(): yayında olan oyunlar

KLASOR = VERI / "turkce"
YORUMLAR, DURUM = KLASOR / "yorumlar.jsonl", KLASOR / "durum.csv"
HEDEF_YORUM, BEKLEME_SN = 200, 2


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    KLASOR.mkdir(exist_ok=True)
    bitmis = set()
    if DURUM.exists():
        with open(DURUM, encoding="utf-8", newline="") as f:
            bitmis = {s["oyun_id"] for s in csv.DictReader(f) if s["durum"] == "tamam"}
    adaylar = y07.adaylari_oku()
    yapilacak = [(o, p) for o, p in adaylar if o not in bitmis]
    print(f"{len(adaylar)} oyun, {len(bitmis)} bitmiş, şimdi {len(yapilacak)} oyun.", flush=True)

    yeni = not DURUM.exists()
    with open(YORUMLAR, "a", encoding="utf-8") as f_y, open(DURUM, "a", encoding="utf-8", newline="") as f_d:
        yaz = csv.writer(f_d)
        if yeni:
            yaz.writerow(["oyun_id", "play_id", "durum", "yorum_sayisi"])
        for sira, (oyun_id, play_id) in enumerate(yapilacak, 1):
            try:
                gelen, _ = reviews(play_id, lang="tr", country="tr", sort=Sort.MOST_RELEVANT, count=HEDEF_YORUM)
            except Exception as hata:                       # geçici hata: tekrar çalıştırınca denenir
                print(f"[{sira}] {play_id}: HATA {str(hata)[:100]}", flush=True)
                yaz.writerow([oyun_id, play_id, "hata", 0]); f_d.flush()
                time.sleep(BEKLEME_SN * 3)
                continue
            for y in gelen:
                if y.get("content"):
                    f_y.write(json.dumps({"oyun_id": oyun_id, "play_id": play_id, "metin": y["content"],
                                          "yildiz": y["score"], "faydali_oy": y["thumbsUpCount"]},
                                         ensure_ascii=False) + "\n")
            yaz.writerow([oyun_id, play_id, "tamam", len(gelen)]); f_y.flush(); f_d.flush()
            if sira % 25 == 0:
                print(f"[{sira}/{len(yapilacak)}] {play_id}: {len(gelen)} yorum", flush=True)
            time.sleep(BEKLEME_SN)
    print("bitti", flush=True)


if __name__ == "__main__":
    main()
