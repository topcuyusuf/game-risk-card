"""Adım 22: Mağaza sinyalleri oyuncu oylarıyla ne kadar örtüşüyor?

Her (sinyal -> tuzak) çifti için, sinyalin ölçülebildiği ve etiketi bilinen oyunlarda:
  isabet  : sinyal varken tuzağın 'var' olma oranı
  taban   : tuzağın genel 'var' oranı (aynı oyunlarda)
  yakalama: 'var' etiketli oyunların kaçında sinyal var
Kullanım:  python src/22_sinyal_karsilastir.py
"""

import json
import re

import pandas as pd

from ortak import HEDEF_TUZAKLAR, VERI


def urun(kalip):
    k = re.compile(kalip, re.I)
    return lambda s: any(k.search(u["ad"]) for u in s["urunler"])


def etiket(ad):
    return lambda s: any(ad in e for e in s["ios_etiketler"])


def kategori(*adlar):
    return lambda s: any(a in s["play_kategoriler"] for a in adlar)


# (sinyal adı, kaynak, tuzak id, fonksiyon). kaynak: hangi oyunlarda ölçülebilir
SINYALLER = [
    ("Apple: Loot Boxes", "ios", 49, etiket("Loot Boxes")),
    ("Apple: Simulated Gambling", "ios", 49, etiket("Simulated Gambling")),
    ("Ürün: chest/crate/box/gacha/summon", "urun", 49, urun(r"chest|crate|\bbox|gacha|summon|\bpull|spin|lucky")),
    ("Apple: Contests", "ios", 54, etiket("Contests")),
    ("Play: Competitive multiplayer", "play", 54, kategori("Competitive multiplayer", "Competitive")),
    ("Play: Competitive multiplayer", "play", 28, kategori("Competitive multiplayer", "Competitive")),
    ("Play: Multiplayer (herhangi)", "play", 21, kategori("Multiplayer", "Cooperative multiplayer", "Competitive multiplayer")),
    ("Play: Offline DEĞİL", "play", 28, lambda s: "Offline" not in s["play_kategoriler"]),
    ("Ürün: remove/no ads", "urun", 13, urun(r"remove ads?|no ads?|ad[- ]?free|\bads?\b")),
    ("Ürün: energy/stamina/lives/refill", "urun", 30, urun(r"energy|stamina|\blives\b|refill|skip|speed ?up")),
    ("Ürün: daily/monthly/subscription/vip", "urun", 11, urun(r"daily|monthly|month|subscription|\bvip\b|weekly")),
    ("Ürün: pass/season", "urun", 45, urun(r"\bpass\b|season")),
    ("Ürün: offer/special/sale/limited/event/starter", "urun", 53, urun(r"offer|special|\bsale\b|limited|event|starter")),
    ("Ürün: herhangi bir ürün >= $49.99", "urun", 24,
     lambda s: any(float(re.sub(r"[^0-9.]", "", u["fiyat"]) or 0) >= 49.99 for u in s["urunler"])),
]


def main():
    tablo = pd.read_pickle(VERI / "oyun_tablosu.pkl").set_index("oyun_id")
    S = {json.loads(s)["oyun_id"]: json.loads(s) for s in open(VERI / "magaza_sinyal.jsonl", encoding="utf-8")}
    olculur = {"ios": lambda s: s["ios_var"], "urun": lambda s: bool(s["urunler"]),
               "play": lambda s: bool(s["play_kategoriler"])}

    satirlar = []
    for ad, kaynak, t, f in SINYALLER:
        ids = [o for o in tablo.index if olculur[kaynak](S[o]) and pd.notna(tablo.loc[o, f"t{t}"])]
        y = tablo.loc[ids, f"t{t}"].astype(int)
        sinyal = pd.Series([f(S[o]) for o in ids], index=ids)
        satirlar.append({
            "sinyal": ad, "tuzak": HEDEF_TUZAKLAR[t], "oyun": len(ids), "sinyalli": int(sinyal.sum()),
            "isabet": y[sinyal].mean(), "taban": y.mean(), "yakalama": sinyal[y == 1].mean(),
            "sinyalsizde_var": y[~sinyal].mean(),
        })
    df = pd.DataFrame(satirlar)
    df.to_csv(VERI / "sonuclar_magaza_sinyal.csv", index=False, encoding="utf-8")
    pd.set_option("display.width", 220)
    print(df.to_string(index=False, float_format="%.2f"))


if __name__ == "__main__":
    main()
