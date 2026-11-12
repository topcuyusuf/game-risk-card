"""Adım 2: Her oyun sayfasına girip tuzak oylarını (VAR / YOK) toplar.

Kullanım:  python src/02_oy_sayilari.py --adet 5
           (--adet verilmezse listedeki tüm oyunlar; kaldığı yerden devam eder)
"""

import argparse
import csv
import re

from bs4 import BeautifulSoup

from ortak import VERI, sayfa_getir

LINKLER = VERI / "oyun_linkleri.csv"
OYLAR = VERI / "tuzak_oylari.csv"       # Her satır: bir oyun + bir tuzak
DURUM = VERI / "oyun_durum.csv"         # Her satır: bir oyun (gezildi mi?)

OY_DESENI = re.compile(r"(\d+)\s*/\s*(\d+)\s*votes")


def oylari_ayikla(html):
    """Oyun sayfasındaki her tuzak için (tuzak_id, ad, var, yok) döndürür."""
    soup = BeautifulSoup(html, "html.parser")
    sonuc = []
    for skor in soup.select("div.face_score"):
        kutu = skor.find_parent("div", class_="flex")
        link = kutu.select_one("a.hoverline") if kutu else None
        eslesme = OY_DESENI.search(skor.get_text(" ", strip=True))
        if not (link and eslesme):
            continue
        tuzak_id = re.match(r"/pattern/(\d+)/", link["href"]).group(1)
        sonuc.append((tuzak_id, link.get_text(strip=True),
                      int(eslesme.group(1)), int(eslesme.group(2))))
    return sonuc


def magaza_idleri(html):
    """Sayfadaki Google Play ve App Store linklerinden uygulama kimliklerini çıkarır."""
    play = re.search(r"play\.google\.com/store/apps/details\?id=([\w.]+)", html)
    ios = re.search(r"apps\.apple\.com/[^\"']*/id(\d+)", html)
    return (play.group(1) if play else ""), (ios.group(1) if ios else "")


def csv_ac(yol, basliklar):
    """Dosyayı ekleme modunda açar; yeni dosyaysa başlık satırını yazar."""
    yeni = not yol.exists()
    f = open(yol, "a", encoding="utf-8", newline="")
    yazici = csv.writer(f)
    if yeni:
        yazici.writerow(basliklar)
    return f, yazici


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--adet", type=int, default=None, help="En fazla kaç oyun")
    args = parser.parse_args()

    with open(LINKLER, encoding="utf-8", newline="") as f:
        oyunlar = list(csv.DictReader(f))

    bitmis = set()
    if DURUM.exists():
        with open(DURUM, encoding="utf-8", newline="") as f:
            bitmis = {s["oyun_id"] for s in csv.DictReader(f)}

    yapilacak = [o for o in oyunlar if o["oyun_id"] not in bitmis]
    if args.adet:
        yapilacak = yapilacak[: args.adet]
    print(f"{len(oyunlar)} oyun var, {len(bitmis)} bitmiş, şimdi {len(yapilacak)} gezilecek.")
    print(f"Tahmini süre: ~{len(yapilacak) * 5 / 60:.0f} dakika")

    f_oy, oy_yaz = csv_ac(OYLAR, ["oyun_id", "tuzak_id", "tuzak_adi", "var", "yok"])
    f_dr, dr_yaz = csv_ac(DURUM, ["oyun_id", "durum", "tuzak_sayisi", "play_id", "ios_id"])

    for sira, oyun in enumerate(yapilacak, 1):
        html = sayfa_getir(oyun["yol"])
        if html is None:
            dr_yaz.writerow([oyun["oyun_id"], "hata", 0, "", ""])
            continue
        tuzaklar = oylari_ayikla(html)
        for tuzak_id, ad, var, yok in tuzaklar:
            oy_yaz.writerow([oyun["oyun_id"], tuzak_id, ad, var, yok])
        play_id, ios_id = magaza_idleri(html)
        dr_yaz.writerow([oyun["oyun_id"], "tamam", len(tuzaklar), play_id, ios_id])
        f_oy.flush()
        f_dr.flush()
        print(f"[{sira}/{len(yapilacak)}] {oyun['yol']}: {len(tuzaklar)} tuzak, "
              f"play={play_id or '-'}")

    f_oy.close()
    f_dr.close()


if __name__ == "__main__":
    main()
