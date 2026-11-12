"""Tüm toplama kodlarının ortak kullandığı ayarlar ve yardımcılar."""

import time
from pathlib import Path

import requests

# --- Ayarlar ---------------------------------------------------------------
SITE = "https://www.darkpattern.games"
BEKLEME_SN = 5  # Site sahibinin şartı: istekler arası en az 5 saniye.
BASLIK = {"User-Agent": "uygulama-risk-karti egitim projesi (ticari degil)"}

# Proje kök klasörü ve veri klasörü (bu dosyanın bir üst klasörü = proje kökü).
KOK = Path(__file__).resolve().parent.parent
VERI = KOK / "data"
VERI.mkdir(exist_ok=True)

# Ekran süresini artıran 14 tuzak: {sitedeki id: ad}
HEDEF_TUZAKLAR = {
    # Zamansal
    10: "Playing by Appointment",
    11: "Daily Rewards",
    12: "Grinding",
    13: "Advertisements",
    14: "Infinite Treadmill",
    28: "Can't Pause or Save",
    30: "Wait To Play",
    # Sosyal
    53: "Fear of Missing Out",
    21: "Social Obligation / Guilds",
    54: "Competition",
    # Psikolojik
    49: "Variable Rewards",
    24: "Invested / Endowed Value",
    45: "Badges / Endowed Progress",
    46: "Complete the Collection",
}

_son_istek = 0.0  # Son isteğin zamanı (saniye).


def sayfa_getir(yol):
    """Siteden bir sayfa çeker; önceki istekten bu yana 5 sn geçmesini bekler."""
    global _son_istek
    gecen = time.time() - _son_istek
    if gecen < BEKLEME_SN:
        time.sleep(BEKLEME_SN - gecen)

    for deneme in range(3):  # Ağ hatasında en fazla 3 deneme.
        try:
            yanit = requests.get(SITE + yol, headers=BASLIK, timeout=30)
            _son_istek = time.time()
            yanit.raise_for_status()
            return yanit.text
        except requests.RequestException as hata:
            _son_istek = time.time()
            print(f"  ! Hata ({deneme + 1}/3): {hata}")
            time.sleep(BEKLEME_SN * (deneme + 2))  # Her denemede daha uzun bekle.
    return None
