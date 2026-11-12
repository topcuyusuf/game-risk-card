"""Adım 1: games.php liste sayfalarından oyun linklerini toplar.

Kullanım:  python src/01_oyun_linkleri.py --liste dark --sadece-puanli
           (puanı olan = oy almış oyunlar bitene kadar gezer; ~61 sayfa)
           python src/01_oyun_linkleri.py --liste healthy --sadece-puanli
           python src/01_oyun_linkleri.py --rastgele 25
           (kura ile 25 sayfa = ~500 oyunluk örneklem)
"""

import argparse
import csv
import itertools
import random
import re

from bs4 import BeautifulSoup

from ortak import VERI, sayfa_getir

DOSYA = VERI / "oyun_linkleri.csv"
SAYFA_BASINA = 20  # Site her listede 20 oyun gösteriyor.
BASLIKLAR = ["oyun_id", "ad", "android", "yol", "liste", "liste_start"]


def mevcut_kayitlari_oku():
    """Daha önce toplanan oyunları ve bitmiş (liste, sayfa) çiftlerini okur."""
    oyunlar, bitmis_sayfalar = {}, set()
    if DOSYA.exists():
        with open(DOSYA, encoding="utf-8", newline="") as f:
            for satir in csv.DictReader(f):
                oyunlar[satir["oyun_id"]] = satir
                bitmis_sayfalar.add((satir["liste"], int(satir["liste_start"])))
    return oyunlar, bitmis_sayfalar


def oyunlari_ayikla(html):
    """Liste sayfasındaki her oyun kutusundan id, ad, Android bilgisi, yol ve puanı çıkarır.

    Not: Puan sadece 'oy almış mı?' filtresi için kullanılır, dosyaya YAZILMAZ.
    (Oylardan türetilen bir sayı; modele girerse veri sızıntısı olur.)
    """
    soup = BeautifulSoup(html, "html.parser")
    sonuc = []
    for kutu in soup.select("a.gamebox"):
        eslesme = re.match(r"/game/(\d+)/", kutu["href"])
        if not eslesme:
            continue
        sonuc.append({
            "oyun_id": eslesme.group(1),
            "ad": kutu.select_one("div.details b").get_text(strip=True),
            "android": 1 if kutu.select_one("i.fa-android") else 0,
            "yol": kutu["href"],
            "puan": float(kutu.select_one("div.ratingNum").get_text(strip=True)),
        })
    return sonuc


def son_start_bul(liste):
    """Liste sayfasındaki sayfalama linklerinden son sayfanın start değerini bulur."""
    html = sayfa_getir(f"/games.php?alignment={liste}")
    degerler = re.findall(rf"start=(\d+)&(?:amp;)?alignment={liste}", html)
    return max(int(d) for d in degerler)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--liste", choices=["dark", "healthy"], default="dark")
    parser.add_argument("--sayfa", type=int, default=None, help="En fazla kaç liste sayfası")
    parser.add_argument("--sadece-puanli", action="store_true",
                        help="Sadece puanı olan (oy almış) oyunları kaydet, bitince dur")
    parser.add_argument("--rastgele", type=int, default=None,
                        help="Sırayla değil, kura ile bu kadar sayfa seç")
    parser.add_argument("--tohum", type=int, default=42,
                        help="Kura tohumu: aynı tohum = aynı sayfalar")
    args = parser.parse_args()

    oyunlar, bitmis = mevcut_kayitlari_oku()
    print(f"Mevcut: {len(oyunlar)} oyun, {len(bitmis)} sayfa bitmiş.")

    if args.rastgele:
        son = son_start_bul(args.liste)
        tum_sayfalar = list(range(0, son + 1, SAYFA_BASINA))
        kura = random.Random(args.tohum)
        secilen = sorted(kura.sample(tum_sayfalar, args.rastgele))
        print(f"{len(tum_sayfalar)} sayfadan {len(secilen)} tanesi seçildi: {secilen}")
        siradaki_sayfalar = iter(secilen)
    else:
        siradaki_sayfalar = itertools.count(0, SAYFA_BASINA)  # 0, 20, 40, ...

    yeni_dosya = not DOSYA.exists()
    with open(DOSYA, "a", encoding="utf-8", newline="") as f:
        yazici = csv.DictWriter(f, fieldnames=BASLIKLAR, extrasaction="ignore")
        if yeni_dosya:
            yazici.writeheader()

        gezilen = 0
        for start in siradaki_sayfalar:
            if args.sayfa is not None and gezilen >= args.sayfa:
                break
            if (args.liste, start) in bitmis:   # Bu sayfa önceden toplandıysa atla.
                continue

            html = sayfa_getir(f"/games.php?start={start}&alignment={args.liste}")
            if html is None:
                print(f"start={start} alınamadı, duruyorum.")
                break

            kayitlar = oyunlari_ayikla(html)
            if not kayitlar:                    # Boş sayfa = listenin sonu.
                print("Listenin sonuna gelindi.")
                break
            if args.sadece_puanli:
                kayitlar = [k for k in kayitlar if k["puan"] != 0]

            yeni = 0
            for k in kayitlar:
                if k["oyun_id"] not in oyunlar:
                    k.update(liste=args.liste, liste_start=start)
                    oyunlar[k["oyun_id"]] = k
                    yazici.writerow(k)
                    yeni += 1
            f.flush()                           # Her sayfadan sonra diske yaz.
            print(f"[{args.liste}] start={start}: {len(kayitlar)} oyun, {yeni} yeni. "
                  f"Toplam {len(oyunlar)}")
            gezilen += 1

            if args.sadece_puanli and not kayitlar:
                print("Puanlı oyunlar bitti.")
                break


if __name__ == "__main__":
    main()
