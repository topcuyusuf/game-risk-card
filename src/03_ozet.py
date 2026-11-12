"""Adım 3: Kaç oyunun yeterli oyu var? (İnternete bağlanmaz, sadece CSV okur.)"""

import csv
from collections import defaultdict

from ortak import HEDEF_TUZAKLAR, VERI

MIN_OY = 2  # Etiket kuralı: bir tuzak için en az 2 oy (var + yok).

# Gezilmiş (başarılı) oyunlar
with open(VERI / "oyun_durum.csv", encoding="utf-8", newline="") as f:
    gezilen = {s["oyun_id"] for s in csv.DictReader(f) if s["durum"] == "tamam"}

# Her oyun için: en çok oy alan tuzağın oyu ve yeterli oylu hedef tuzak sayısı
en_cok_oy = defaultdict(int)
yeterli_hedef = defaultdict(int)
with open(VERI / "tuzak_oylari.csv", encoding="utf-8", newline="") as f:
    for s in csv.DictReader(f):
        toplam = int(s["var"]) + int(s["yok"])
        en_cok_oy[s["oyun_id"]] = max(en_cok_oy[s["oyun_id"]], toplam)
        if int(s["tuzak_id"]) in HEDEF_TUZAKLAR and toplam >= MIN_OY:
            yeterli_hedef[s["oyun_id"]] += 1

n = len(gezilen)
print(f"Gezilen oyun: {n}")
print(f"Hiç oy almamış oyun: {sum(1 for o in gezilen if en_cok_oy[o] == 0)}")
print()
print("En az bir tuzağı şu kadar oy almış oyun sayısı (yaklaşık 'oy veren kişi'):")
for esik in [1, 2, 3, 5, 10]:
    k = sum(1 for o in gezilen if en_cok_oy[o] >= esik)
    print(f"  >= {esik:>2} oy: {k:>6}  (%{100 * k / max(n, 1):.1f})")
print()
k = sum(1 for o in gezilen if yeterli_hedef[o] >= 1)
print(f"14 hedef tuzaktan en az birinde >= {MIN_OY} oy olan oyun: {k} (%{100 * k / max(n, 1):.1f})")
k = sum(1 for o in gezilen if yeterli_hedef[o] == len(HEDEF_TUZAKLAR))
print(f"14 hedef tuzağın hepsinde >= {MIN_OY} oy olan oyun: {k}")
