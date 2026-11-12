"""Adım 4: Puana göre sıralı listede, puanın 0.00'a düştüğü sınırı ikiye bölerek bulur.

Puanı 0.00 olmayan oyun = en az bir oy almış oyun.
Kullanım:  python src/04_sinir_bul.py
"""

import re

from bs4 import BeautifulSoup

from ortak import sayfa_getir

SAYFA_BASINA = 20


def puanlari_oku(liste, start):
    """Bir liste sayfasındaki 20 oyunun puanlarını (sayı olarak) döndürür."""
    html = sayfa_getir(f"/games.php?start={start}&alignment={liste}")
    soup = BeautifulSoup(html, "html.parser")
    return [float(k.select_one("div.ratingNum").get_text(strip=True))
            for k in soup.select("a.gamebox")]


def son_start(liste):
    """Listenin son sayfasının start değerini sayfalama linklerinden okur."""
    html = sayfa_getir(f"/games.php?alignment={liste}")
    return max(int(d) for d in re.findall(rf"start=(\d+)&(?:amp;)?alignment={liste}", html))


def sinir_bul(liste):
    """Puanı 0 olmayan oyunların kaç tane olduğunu bulur."""
    # alt: puanlı olduğunu bildiğimiz sayfa, ust: tamamı 0.00 olduğunu bildiğimiz sayfa
    alt, ust = 0, son_start(liste)
    print(f"\n[{liste}] Son sayfa start={ust}")

    while ust - alt > SAYFA_BASINA:
        orta = (alt + ust) // 2 // SAYFA_BASINA * SAYFA_BASINA  # 20'nin katına yuvarla
        puanlar = puanlari_oku(liste, orta)
        sifir_degil = sum(1 for p in puanlar if p != 0)
        print(f"  start={orta:>5}: {sifir_degil}/{len(puanlar)} oyunun puanı var")
        if sifir_degil > 0:
            alt = orta      # Sınır daha arkada.
        else:
            ust = orta      # Sınır daha önde.

    # Sınır sayfası 'alt': içinde kaç puanlı oyun olduğunu say.
    puanlar = puanlari_oku(liste, alt)
    son_sayfadaki = sum(1 for p in puanlar if p != 0)
    toplam = alt + son_sayfadaki
    print(f"  Sınır sayfası start={alt}: {son_sayfadaki} puanlı oyun")
    print(f"  => [{liste}] listesinde puanlı (oylu) oyun: {toplam}")
    return toplam


if __name__ == "__main__":
    karanlik = sinir_bul("dark")
    saglikli = sinir_bul("healthy")
    print(f"\nKaranlık: {karanlik}, Sağlıklı: {saglikli}, Toplam: {karanlik + saglikli}")
