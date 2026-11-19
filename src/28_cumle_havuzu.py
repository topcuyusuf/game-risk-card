"""Adım 28: Cümle düzeyinde etiket için aday havuzu (pilot: Can't Pause or Save).

Sorun: oyun düzeyindeki etiketle eğitilen modeller tuzağın kendisini değil 'karanlık oyun'u öğreniyor.
Çözüm denemesi: tek tek CÜMLELERE "bu cümle tuzaktan bahsediyor mu?" etiketi vermek.
Sadece GELİŞTİRME oyunları kullanılır; bağımsız test (iOS) dokunulmadan kalır.

Havuz üç gruptan oluşur:
  A) kelime kuralına uyan cümleler          -> kural ne kadar yanılıyor?
  B) tuzağı olan oyunlarda, kurala UYMAYAN ama
     konuyla ilgili kelime geçen cümleler     -> kural neyi kaçırıyor?
  C) rastgele cümleler                       -> genel taban
Kullanım:  python src/28_cumle_havuzu.py
"""

import importlib
import random
import re
import sys

import pandas as pd

from ortak import VERI

kanit_mod = importlib.import_module("15_kanitlar")

TUZAK = 28
ILGILI = re.compile(r"\b(?:pause|paus(?:ed|ing)|save[sd]?|saving|progress|quit|leav(?:e|ing)|exit"
                    r"|offline|internet|connection|wifi|reset|restart|lost|afk|kick(?:ed)?)\b", re.I)
ADET = {"A": 60, "B": 60, "C": 30}
KLASOR = VERI / "cumle"


def cumleler(metin):
    """Yorumu cümlelere böler; çok kısa parçalar atılır."""
    return [c.strip() for c in re.split(r"(?<=[.!?])\s+|\n+", metin) if len(c.strip().split()) >= 4]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    tablo = pd.read_pickle(VERI / "oyun_tablosu.pkl")
    kural = kanit_mod.KURALLAR[TUZAK]
    gruplar = {"A": [], "B": [], "C": []}
    for _, s in tablo.iterrows():
        var = s[f"t{TUZAK}"] == 1
        for y in s["yorumlar"]:
            for c in cumleler(y):
                if kanit_mod.olumlu_eslesme(kural, c):
                    gruplar["A"].append((s["oyun_id"], c))
                elif var and ILGILI.search(c):
                    gruplar["B"].append((s["oyun_id"], c))
                else:
                    gruplar["C"].append((s["oyun_id"], c))
    r = random.Random(42)
    satir = []
    for g, n in ADET.items():
        print(f"{g}: havuzda {len(gruplar[g])} cümle, {n} seçildi")
        for oyun_id, c in r.sample(gruplar[g], n):
            satir.append({"grup": g, "oyun_id": oyun_id, "cumle": c[:400]})
    r.shuffle(satir)                       # Etiketlerken grup bilinmesin
    df = pd.DataFrame(satir)
    df.insert(0, "no", range(1, len(df) + 1))
    df["etiket"] = ""
    KLASOR.mkdir(exist_ok=True)
    df.to_csv(KLASOR / f"havuz_t{TUZAK}.csv", index=False, encoding="utf-8-sig")
    print("->", KLASOR / f"havuz_t{TUZAK}.csv")


if __name__ == "__main__":
    main()
