"""Adım 8: Yorumu toplanan oyunlar için 14 tuzağın etiketlerini çıkarır.

Kural: en az 2 oy (var + yok) VE var > yok  -> 1
       en az 2 oy VE var < yok               -> 0
       var == yok (oylar eşit)               -> boş (bilinmiyor; oyuncular anlaşamamış)
       2'den az oy                           -> boş (bilinmiyor; 0 DEĞİL)
Sitede hiç görünmeyen tuzak = 0 oy = bilinmiyor.
Kullanım:  python src/08_etiketler.py
"""

import csv
from collections import defaultdict

from ortak import HEDEF_TUZAKLAR, VERI

MIN_OY = 2
CIKTI = VERI / "etiketler.csv"


def etiket(var, yok):
    """Bir oyun-tuzak çifti için 1, 0 ya da None (bilinmiyor) döndürür."""
    if var + yok < MIN_OY or var == yok:
        return None
    return 1 if var > yok else 0


def main():
    # 1) Yorumu olan oyunlar (modelin göreceği oyunlar)
    with open(VERI / "yorum_durum.csv", encoding="utf-8", newline="") as f:
        oyunlar = [s["oyun_id"] for s in csv.DictReader(f)
                   if s["durum"] == "tamam" and int(s["yorum_sayisi"]) > 0]
    with open(VERI / "oyun_linkleri.csv", encoding="utf-8", newline="") as f:
        liste = {s["oyun_id"]: s["liste"] for s in csv.DictReader(f)}

    # 2) Oylar: (oyun, tuzak) -> (var, yok). Kayıt yoksa (0, 0).
    oylar = defaultdict(lambda: (0, 0))
    with open(VERI / "tuzak_oylari.csv", encoding="utf-8", newline="") as f:
        for s in csv.DictReader(f):
            oylar[(s["oyun_id"], int(s["tuzak_id"]))] = (int(s["var"]), int(s["yok"]))

    # 3) Etiket tablosu: her satır bir oyun, her sütun bir tuzak
    sayac = {t: {"1": 0, "0": 0, "bos": 0, "esit": 0} for t in HEDEF_TUZAKLAR}
    with open(CIKTI, "w", encoding="utf-8", newline="") as f:
        yazici = csv.writer(f)
        yazici.writerow(["oyun_id", "liste"] + [f"t{t}" for t in HEDEF_TUZAKLAR])
        for oyun in oyunlar:
            satir = [oyun, liste[oyun]]
            for t in HEDEF_TUZAKLAR:
                var, yok = oylar[(oyun, t)]
                e = etiket(var, yok)
                satir.append("" if e is None else e)
                sayac[t]["bos" if e is None else str(e)] += 1
                if var + yok >= MIN_OY and var == yok:   # Bilinmiyor'un içindeki eşitler
                    sayac[t]["esit"] += 1
            yazici.writerow(satir)

    # 4) Özet
    print(f"{len(oyunlar)} oyun etiketlendi -> {CIKTI.name}\n")
    print(f"{'Tuzak':<28}{'var(1)':>7}{'yok(0)':>7}{'bilinmiyor':>11}{'(eşit)':>7}{'%var':>6}")
    for t, ad in HEDEF_TUZAKLAR.items():
        s = sayac[t]
        bilinen = s["1"] + s["0"]
        print(f"{ad:<28}{s['1']:>7}{s['0']:>7}{s['bos']:>11}{s['esit']:>7}"
              f"{100 * s['1'] / max(bilinen, 1):>5.0f}%")


if __name__ == "__main__":
    main()
