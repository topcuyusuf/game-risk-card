"""Adım 36: Open Play'deki Steam oyunlarının Google Play sürümlerini bulur ve yorumlarını toplar.

Amaç: kartı gerçek oynama süresine karşı daha fazla oyunda sınamak (35. adımda 60 oyun vardı).
Bu oyunlar darkpattern.games kartlarımızda yok -> dondurulmuş sistem bunları hiç görmedi (temiz test).
Eşleştirme sıkı: Play'deki adın sadeleştirilmiş hali Steam adıyla AYNI olmalı ve uygulama oyun olmalı.
Yalnızca Google Play'e istek atılır (2 sn arayla). Kullanıcı adı/fotoğraf kaydedilmez. Kaldığı yerden devam eder.
Aşamalar:  python src/36_open_play_play.py esle      (Play'de ara, eşleştir)
           python src/36_open_play_play.py yorum     (eşleşenlerin 200 yorumu)
"""

import argparse
import csv
import importlib
import io
import json
import re
import sys
import time
import zipfile

import numpy as np
import pandas as pd
import requests
from google_play_scraper import Sort, app, reviews
from google_play_scraper.exceptions import NotFoundError

from ortak import VERI

op = importlib.import_module("34_open_play")

KLASOR = VERI / "open_play_play"
ESLESME, YORUMLAR, YORUM_DURUM = KLASOR / "eslesme.csv", KLASOR / "yorumlar.jsonl", KLASOR / "yorum_durum.csv"
MIN_KISI, BEKLEME = 10, 2

# Elle kontrol (71 "kabul"ün gözden geçirilmesi): sade() alt başlığı attığı için bazıları FARKLI oyun / kopya çıktı.
# Yalnızca aynı oyunun resmî mobil sürümü bırakılır; aşağıdakiler atılır.
ELLE_RET = {
    "com.ghostshippublishing.deeprockgalacticsurvivor": "farklı oyun (Survivor)",
    "com.winwaed.spacewar": "Steam 'Spacewar' bir test uygulaması",
    "com.direwolfdigital.dune": "farklı oyun (Dune: Imperium)",
    "com.paradoxplaza.lassie": "farklı oyun (Galaxy Command)",
    "com.nokope.supermarket.simulator": "geliştirici farklı (kopya olabilir)",
    "com.zgs.truck.simulator.game": "kopya (SCS mobil sürüm yapmadı)",
    "com.imaginalis.HouseFlipperMobile": "farklı oyun (Home Design)",
    "com.telltalegames.batman100": "farklı oyun (Telltale)",
    "com.CPZTApps.Blender": "oyun değil / kopya",
    "com.blockot.worldwar.winter.sniper": "kopya",
    "com.dmg.crimescenecleaner": "kopya (Mobile 3D)",
    "com.neuroticfly.interdimensionalvendingmachine": "farklı oyun",
    "com.PHANTOMPRODUCTIONSYAZILIMLIMITEDSIRKETI.Haste": "kopya",
    "com.playgama.prisonarchitect": "farklı oyun (Cage Break)",
    "com.retroarch": "emülatör, oyun değil",
    "com.ggs.quarantine.zombie.simulator": "kopya",
    "com.pid.vmcony": "farklı oyun (CoNY)",
    "com.Ultragames.SnowRunner": "kopya",
    "com.ahmmmad.gameecarrr": "kopya",
    "com.mbproperties.farming.tractors.farmingsimulator": "kopya",
    "com.com2us.frostpunk.android.google.global.normal": "farklı oyun (Beyond the Ice)",
    "com.feralinteractive.hitmanbloodmoney_android": "farklı oyun (Blood Money)",
    "com.bethsoft.DOOM": "belirsiz (1993 / 2016 aynı ada düşüyor)",
}


def steam_oyunlari():
    """Steam'de en az MIN_KISI oyuncusu olan oyunlar: anahtar, görünen ad, kişi sayısı, göreli süre."""
    z = zipfile.ZipFile(op.ZIP)
    st = pd.read_csv(io.BytesIO(z.read(op.ON + "steam.csv.gz")), compression="gzip",
                     usecols=["pid", "title_id", "minutes"])
    st["anahtar"] = st.title_id.map(op.sade)
    st = st[(st.anahtar != "") & (st.minutes > 0)]
    kp = st.groupby(["pid", "anahtar"]).minutes.sum().reset_index()
    kp["log_rel"] = np.log(kp.minutes) - kp.groupby("pid").minutes.transform(lambda m: np.log(m).mean())
    g = kp.groupby("anahtar").agg(kisi=("pid", "nunique"), log_rel=("log_rel", "mean"))
    g["ad"] = st.groupby("anahtar").title_id.agg(lambda s: s.value_counts().index[0])
    return g[g.kisi >= MIN_KISI].sort_values("kisi", ascending=False)


def play_ara(metin):
    r = requests.get("https://play.google.com/store/search", params={"q": metin, "c": "apps", "hl": "en", "gl": "us"},
                     headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    return list(dict.fromkeys(re.findall(r"/store/apps/details\?id=([\w.]+)", r.text)))[:3] if r.ok else []


def esle():
    KLASOR.mkdir(exist_ok=True)
    g = steam_oyunlari()
    with open(VERI / "oyun_linkleri.csv", encoding="utf-8", newline="") as f:
        bizim = {op.sade(s["ad"]) for s in csv.DictReader(f)}          # zaten kartı olanlar (35. adım) atlanır
    bakilan = set(pd.read_csv(ESLESME).anahtar) if ESLESME.exists() else set()
    yapilacak = [(k, r.ad) for k, r in g.iterrows() if k not in bizim and k not in bakilan]
    print(f"Steam oyunu (>= {MIN_KISI} kişi): {len(g)} | kartımız olan: {sum(k in bizim for k in g.index)} | "
          f"bakılmış: {len(bakilan)} | şimdi: {len(yapilacak)}", flush=True)
    yeni = not ESLESME.exists()
    with open(ESLESME, "a", encoding="utf-8", newline="") as f:
        yaz = csv.writer(f)
        if yeni:
            yaz.writerow(["anahtar", "steam_ad", "play_id", "play_ad", "tur", "sonuc"])
        for sira, (k, ad) in enumerate(yapilacak, 1):
            sonuc, pid, pad, tur = "yok", "", "", ""
            try:
                adaylar = play_ara(ad)
                time.sleep(BEKLEME)
                for aday in adaylar:
                    try:
                        b = app(aday, lang="en", country="us")
                    except NotFoundError:
                        continue
                    time.sleep(BEKLEME)
                    if op.sade(b.get("title")) == k:
                        pid, pad, tur = aday, b.get("title"), b.get("genreId", "")
                        sonuc = "kabul" if str(tur).startswith("GAME") else "oyun_degil"
                        break
            except Exception as hata:
                sonuc = "hata"
                print("  !", str(hata)[:100], flush=True)
            if sonuc != "hata":
                yaz.writerow([k, ad, pid, pad, tur, sonuc]); f.flush()
            if sira % 25 == 0:
                print(f"[{sira}/{len(yapilacak)}] {ad} -> {sonuc}", flush=True)


def yorum():
    e = pd.read_csv(ESLESME)
    e = e[(e.sonuc == "kabul") & ~e.play_id.isin(ELLE_RET)].drop_duplicates("play_id")
    bitmis = set(pd.read_csv(YORUM_DURUM).play_id) if YORUM_DURUM.exists() else set()
    yapilacak = e[~e.play_id.isin(bitmis)]
    print(f"Eşleşen: {len(e)} | yorumu toplanmış: {len(bitmis)} | şimdi: {len(yapilacak)}", flush=True)
    yeni = not YORUM_DURUM.exists()
    with open(YORUMLAR, "a", encoding="utf-8") as f_y, open(YORUM_DURUM, "a", encoding="utf-8", newline="") as f_d:
        yaz = csv.writer(f_d)
        if yeni:
            yaz.writerow(["play_id", "yorum_sayisi"])
        for _, r in yapilacak.iterrows():
            try:
                gelen, _ = reviews(r.play_id, lang="en", country="us", sort=Sort.MOST_RELEVANT, count=200)
            except Exception as hata:
                print("  !", r.play_id, str(hata)[:100], flush=True)
                time.sleep(BEKLEME * 3)
                continue
            for y in gelen:
                if y.get("content"):
                    f_y.write(json.dumps({"play_id": r.play_id, "metin": y["content"], "yildiz": y["score"],
                                          "faydali_oy": y["thumbsUpCount"]}, ensure_ascii=False) + "\n")
            yaz.writerow([r.play_id, len(gelen)]); f_y.flush(); f_d.flush()
            time.sleep(BEKLEME)
    print("bitti", flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser()
    p.add_argument("asama", choices=["esle", "yorum"])
    {"esle": esle, "yorum": yorum}[p.parse_args().asama]()
