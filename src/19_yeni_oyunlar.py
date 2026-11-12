"""Adım 19: darkpattern.games'te HİÇ OYU OLMAYAN oyunlar için risk kartı (asıl yapay zekâ kullanımı).

Aşama 'topla': 500'lük örneklemdeki oysuz oyunların sayfasına girer (5 sn arayla),
               oy olmadığını doğrular, Play kimliğini alır, Play'den bilgi + 200 yorum çeker.
Aşama 'kart' : Modeli bilinen 485 oyunun HEPSİYLE eğitir, yeni oyunlara uygular,
               aynı kanıt ve renk kurallarıyla kart üretir.
Kullanım:  python src/19_yeni_oyunlar.py topla --adet 20
           python src/19_yeni_oyunlar.py kart
"""

import argparse
import csv
import importlib
import json
import random
import re
import time

import pandas as pd
from google_play_scraper import Sort, app, reviews
from google_play_scraper.exceptions import NotFoundError

from ortak import VERI, sayfa_getir

oylar = importlib.import_module("02_oy_sayilari")      # oylari_ayikla, magaza_idleri
veri_seti = importlib.import_module("09_veri_seti")    # html_temizle
ilk_model = importlib.import_module("10_ilk_model")    # model_kur
risk = importlib.import_module("14_risk_skoru")        # genel_karanlik, renk
kanitlar = importlib.import_module("15_kanitlar")      # oyun_kanitlari, yorumlari_sirala
kart_mod = importlib.import_module("16_kart")          # kart_kur, kural_karnesi, renk_cumlesi
import sistem as sistem_mod
magaza_mod = importlib.import_module("21_magaza_sinyalleri")  # apple_lookup, apple_urunler, play_kategoriler

KLASOR = VERI / "yeni"
DENEMELER = KLASOR / "denemeler.csv"       # Her bakılan oyun ve sonucu (kaldığı yerden devam)
OYUNLAR = KLASOR / "oyunlar.jsonl"
YORUMLAR = KLASOR / "yorumlar.jsonl"
KARTLAR = KLASOR / "kartlar.jsonl"
MAGAZA = KLASOR / "magaza_sinyal.jsonl"
MIN_YORUM = 50
PLAY_BEKLEME = 2


def adaylar():
    """Örneklemde oyu olmayan oyunlar, sabit tohumla karıştırılmış sırada."""
    with open(VERI / "orneklem_500" / "oyun_durum.csv", encoding="utf-8", newline="") as f:
        oysuz = {s["oyun_id"] for s in csv.DictReader(f) if s["tuzak_sayisi"] == "0"}
    with open(VERI / "orneklem_500" / "oyun_linkleri.csv", encoding="utf-8", newline="") as f:
        yollar = {s["oyun_id"]: s["yol"] for s in csv.DictReader(f) if s["oyun_id"] in oysuz}
    sirali = sorted(yollar.items())
    random.Random(42).shuffle(sirali)
    return sirali


def topla(adet):
    KLASOR.mkdir(exist_ok=True)
    bakilan, kabul = set(), 0
    if DENEMELER.exists():
        with open(DENEMELER, encoding="utf-8", newline="") as f:
            for s in csv.DictReader(f):
                bakilan.add(s["oyun_id"])
                kabul += s["sonuc"] == "kabul"
    yeni = not DENEMELER.exists()
    with open(DENEMELER, "a", encoding="utf-8", newline="") as f_d, \
         open(OYUNLAR, "a", encoding="utf-8") as f_o, open(YORUMLAR, "a", encoding="utf-8") as f_y:
        yaz = csv.writer(f_d)
        if yeni:
            yaz.writerow(["oyun_id", "play_id", "sonuc"])

        for oyun_id, yol in adaylar():
            if kabul >= adet:
                break
            if oyun_id in bakilan:
                continue
            html = sayfa_getir(yol)
            if html is None:
                continue
            # 1) Oy gerçekten yok mu? (Örneklemden bu yana oy gelmiş olabilir.)
            if oylar.oylari_ayikla(html):
                yaz.writerow([oyun_id, "", "artik_oyu_var"]); f_d.flush(); continue
            play_id, _ = oylar.magaza_idleri(html)
            if not play_id:
                yaz.writerow([oyun_id, "", "play_yok"]); f_d.flush(); continue
            ad = re.search(r"'(.+)' Rating", html)
            # 2) Play'de yayında mı, oyun mu?
            try:
                bilgi = app(play_id, lang="en", country="us")
            except NotFoundError:
                yaz.writerow([oyun_id, play_id, "kaldirilmis"]); f_d.flush(); continue
            if not str(bilgi.get("genreId", "")).startswith("GAME"):
                yaz.writerow([oyun_id, play_id, "oyun_degil"]); f_d.flush(); continue
            time.sleep(PLAY_BEKLEME)
            # 3) Yorumlar
            gelen, _ = reviews(play_id, lang="en", country="us", sort=Sort.MOST_RELEVANT, count=200)
            time.sleep(PLAY_BEKLEME)
            if len(gelen) < MIN_YORUM:
                yaz.writerow([oyun_id, play_id, f"az_yorum_{len(gelen)}"]); f_d.flush(); continue

            f_o.write(json.dumps({
                "oyun_id": oyun_id, "play_id": play_id,
                "ad": bilgi.get("title") or (ad.group(1) if ad else play_id),
                "tur": bilgi.get("genre"), "indirme": bilgi.get("installs"),
                "aciklama": (bilgi.get("summary") or "") + " " + veri_seti.html_temizle(bilgi.get("description")),
            }, ensure_ascii=False) + "\n")
            for y in gelen:
                f_y.write(json.dumps({"oyun_id": oyun_id, "metin": y["content"], "yildiz": y["score"],
                                      "faydali_oy": y["thumbsUpCount"]}, ensure_ascii=False) + "\n")
            yaz.writerow([oyun_id, play_id, "kabul"])
            for f in (f_d, f_o, f_y):
                f.flush()
            kabul += 1
            print(f"[{kabul}/{adet}] {bilgi.get('title')} ({play_id}): {len(gelen)} yorum")


def magaza():
    """Kabul edilen yeni oyunlar için mağaza sinyalleri (21. adımdaki aynı fonksiyonlarla)."""
    yollar = dict(adaylar())
    with open(DENEMELER, encoding="utf-8", newline="") as f:
        kabul = [(s["oyun_id"], s["play_id"]) for s in csv.DictReader(f) if s["sonuc"] == "kabul"]
    bitmis = {json.loads(s)["oyun_id"] for s in open(MAGAZA, encoding="utf-8")} if MAGAZA.exists() else set()
    with open(MAGAZA, "a", encoding="utf-8") as f:
        for oyun_id, play_id in kabul:
            if oyun_id in bitmis:
                continue
            kayit = {"oyun_id": oyun_id, "play_id": play_id, "ios_id": "", "ios_var": False,
                     "ios_etiketler": [], "urunler": [], "play_kategoriler": []}
            try:
                html = sayfa_getir(yollar[oyun_id])              # iOS kimliği için (5 sn kuralı)
                kayit["ios_id"] = oylar.magaza_idleri(html)[1] if html else ""
                if kayit["ios_id"]:
                    bilgi = magaza_mod.apple_lookup(kayit["ios_id"])
                    time.sleep(PLAY_BEKLEME)
                    if bilgi:
                        url = bilgi.pop("ios_url")
                        kayit.update(bilgi, ios_var=True)
                        kayit["urunler"] = magaza_mod.apple_urunler(url)
                        time.sleep(PLAY_BEKLEME)
                kayit["play_kategoriler"] = magaza_mod.play_kategoriler(play_id)
                time.sleep(PLAY_BEKLEME)
            except Exception as hata:
                kayit["hata"] = str(hata)[:150]
            f.write(json.dumps(kayit, ensure_ascii=False) + "\n")
            f.flush()
            print(oyun_id, "ios:", kayit["ios_var"], "etiket:", len(kayit["ios_etiketler"]),
                  "ürün:", len(kayit["urunler"]), "kat:", len(kayit["play_kategoriler"]), kayit.get("hata", ""))


def kart():
    sistem = sistem_mod.sistemi_yukle(yeniden=True)     # 485 oyunla eğit, önbelleğe yaz

    # --- Yeni oyunlar ---
    oyunlar = [json.loads(s) for s in open(OYUNLAR, encoding="utf-8")]
    yorum = {}
    for s in open(YORUMLAR, encoding="utf-8"):
        y = json.loads(s)
        if y["metin"]:
            yorum.setdefault(y["oyun_id"], []).append(y)

    yeni_magaza = {}
    if MAGAZA.exists():
        yeni_magaza = {json.loads(s)["oyun_id"]: json.loads(s) for s in open(MAGAZA, encoding="utf-8")}

    kartlar = []
    for o in oyunlar:
        k = sistem_mod.kart_uret(sistem, o["oyun_id"], o["ad"], yorum[o["oyun_id"]], o["aciklama"],
                                 yeni_magaza.get(o["oyun_id"]))
        k["oysuz"] = True    # darkpattern.games'te oyu yok: kart tamamen tahmin
        kartlar.append(k)

    with open(KARTLAR, "w", encoding="utf-8") as f:
        for k in kartlar:
            f.write(json.dumps(k, ensure_ascii=False) + "\n")

    print(f"{len(kartlar)} yeni oyun için kart -> {KARTLAR}\n")
    for k in sorted(kartlar, key=lambda k: -k["puan"]):
        tespit = ", ".join(f"{p['tuzak']}({p['agirlik']})" for p in k["puan_dokumu"]) or "-"
        print(f"{k['renk']:<8} {k['puan']:>2}/15  model:{k['model_renk']:<8} {k['ad'][:34]:<34} {tespit}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("asama", choices=["topla", "magaza", "kart"])
    p.add_argument("--adet", type=int, default=20)
    a = p.parse_args()
    {"topla": lambda: topla(a.adet), "magaza": magaza, "kart": kart}[a.asama]()
