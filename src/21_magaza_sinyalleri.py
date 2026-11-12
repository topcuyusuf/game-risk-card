"""Adım 21: Oya bağlı OLMAYAN mağaza sinyalleri (darkpattern.games'e istek atmaz).

Her oyun için üç kaynak:
  1) Apple iTunes Lookup (resmî servis): içerik etiketleri (advisories) — "Loot Boxes",
     "Simulated Gambling", "Frequent/Intense Contests" vb.
  2) App Store sayfası: uygulama içi satın alma ürünlerinin adları ve fiyatları.
  3) Google Play: kategori etiketleri ("Competitive multiplayer", "Single player" ...).
Geliştirici/satıcı adı KAYDEDİLMEZ.
Kullanım:  python src/21_magaza_sinyalleri.py --adet 5
"""

import argparse
import csv
import json
import re
import time

import pandas as pd
import requests
from google_play_scraper import app as play_app

from ortak import VERI

CIKTI = VERI / "magaza_sinyal.jsonl"
BEKLEME_SN = 2
BASLIK = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "Chrome/126 Safari/537.36"}
URUN = re.compile(r'\{"\$kind":"textPair","leadingText":"((?:[^"\\]|\\.)*)","trailingText":"((?:[^"\\]|\\.)*)"\}')


def apple_lookup(ios_id):
    """Resmî sorgu servisi: içerik etiketleri ve yaş derecesi."""
    r = requests.get("https://itunes.apple.com/lookup", params={"id": ios_id, "country": "us"},
                     headers=BASLIK, timeout=30)
    sonuc = r.json().get("results", [])
    if not sonuc:
        return None
    s = sonuc[0]
    return {"ios_etiketler": s.get("advisories", []), "ios_yas": s.get("contentAdvisoryRating"),
            "gamecenter": bool(s.get("isGameCenterEnabled")), "ios_url": s.get("trackViewUrl")}


def apple_urunler(url):
    """App Store sayfasındaki 'In-App Purchases' listesinden ürün adı + fiyat."""
    r = requests.get(url, headers=BASLIK, timeout=30)
    h = r.text
    i = h.find('"In-App Purchases","summary"')
    if i < 0:
        return []
    parca = h[i:i + 20000]
    parca = parca[:parca.find("]") + 1]                      # sadece bu listenin öğeleri
    return [{"ad": json.loads(f'"{a}"'), "fiyat": json.loads(f'"{f}"')} for a, f in URUN.findall(parca)]


def play_kategoriler(play_id):
    b = play_app(play_id, lang="en", country="us")
    return [k["name"] for k in b.get("categories", []) if k.get("name")]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--adet", type=int, default=None)
    args = p.parse_args()

    oyunlar = set(pd.read_pickle(VERI / "oyun_tablosu.pkl")["oyun_id"])
    with open(VERI / "oyun_durum.csv", encoding="utf-8", newline="") as f:
        kimlik = {s["oyun_id"]: s for s in csv.DictReader(f) if s["oyun_id"] in oyunlar}

    bitmis = set()
    if CIKTI.exists():
        bitmis = {json.loads(s)["oyun_id"] for s in open(CIKTI, encoding="utf-8")}
    yapilacak = [o for o in sorted(kimlik) if o not in bitmis][: args.adet]
    print(f"{len(kimlik)} oyun, {len(bitmis)} bitmiş, şimdi {len(yapilacak)}")

    with open(CIKTI, "a", encoding="utf-8") as f:
        for sira, oyun_id in enumerate(yapilacak, 1):
            k = kimlik[oyun_id]
            kayit = {"oyun_id": oyun_id, "ios_id": k["ios_id"], "play_id": k["play_id"],
                     "ios_var": False, "ios_etiketler": [], "urunler": [], "play_kategoriler": []}
            try:
                if k["ios_id"]:
                    bilgi = apple_lookup(k["ios_id"])
                    time.sleep(BEKLEME_SN)
                    if bilgi:
                        url = bilgi.pop("ios_url")
                        kayit.update(bilgi, ios_var=True)
                        kayit["urunler"] = apple_urunler(url)
                        time.sleep(BEKLEME_SN)
                kayit["play_kategoriler"] = play_kategoriler(k["play_id"])
                time.sleep(BEKLEME_SN)
            except Exception as hata:
                kayit["hata"] = str(hata)[:150]
            f.write(json.dumps(kayit, ensure_ascii=False) + "\n")
            f.flush()
            print(f"[{sira}/{len(yapilacak)}] {oyun_id}: ios={kayit['ios_var']} "
                  f"etiket={len(kayit['ios_etiketler'])} ürün={len(kayit['urunler'])} "
                  f"play_kat={len(kayit['play_kategoriler'])} {kayit.get('hata', '')}")


if __name__ == "__main__":
    main()
