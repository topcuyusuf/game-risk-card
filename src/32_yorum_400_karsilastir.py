"""Adım 32: Kart 200 yorumla mı, 400 yorumla mı daha iyi? (31. adımda toplanan yeni yorumlarla)

İki sürüm aynı yeni toplamadan gelir, böylece fark yalnızca yorum sayısıdır:
  ilk200 : Play'in 'en alakalı' sırasındaki ilk 200 yorum (bugün 200 istense gelecek olanlar)
  tam400 : 400 yorumun tamamı
Her sürüm için modeller 5 katlı düzende o sürümün metniyle eğitilir; kural karnesi dondurulmuş sistemden.
Kararlılık (200'de, doğrudan ölçüm): 400 yorum ortak yorumu olmayan iki 200'lük gruba bölünür (5 tekrar).
Kullanım:  python src/32_yorum_400_karsilastir.py
"""

import importlib
import json
import random
import sys
from collections import defaultdict

import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold

import sistem as sistem_mod
from ortak import VERI

ilk_model = importlib.import_module("10_ilk_model")
risk = importlib.import_module("14_risk_skoru")
kart_mod = importlib.import_module("16_kart")
deney30 = importlib.import_module("30_yorum_sayisi")      # puanla() aynı

TEKRAR = 5
RENKLER = ["yesil", "sari", "kirmizi"]


def yorumlari_oku():
    y = defaultdict(list)
    for s in open(VERI / "yorum_400" / "yorumlar.jsonl", encoding="utf-8"):
        k = json.loads(s)
        if k.get("metin"):
            y[k["oyun_id"]].append((k["sira"], k["metin"]))
    return {i: [m for _, m in sorted(v)] for i, v in y.items()}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    tablo = pd.read_pickle(VERI / "oyun_tablosu.pkl").reset_index(drop=True)
    tablo["oyun_id"] = tablo["oyun_id"].astype(str)
    yorum = yorumlari_oku()
    tablo = tablo[tablo.oyun_id.isin(yorum)].reset_index(drop=True)
    sayi = tablo.oyun_id.map(lambda i: len(yorum[i]))
    print(f"Oyun: {len(tablo)} | yorum sayısı: en az {sayi.min()}, ortanca {int(sayi.median())}, "
          f"400 olan {int((sayi >= 400).sum())}")

    _, _, _, _, magaza = kart_mod.oku()
    karne = sistem_mod.sistemi_yukle()["karne"]
    y_genel = risk.genel_karanlik(tablo)
    surum = {"ilk200": tablo.oyun_id.map(lambda i: yorum[i][:200]),
             "tam400": tablo.oyun_id.map(lambda i: yorum[i][:400])}
    hedef = {"genel_olas": y_genel, "reklam_olas": tablo["t13"], "durdurma_olas": tablo["t28"]}
    katlar = list(StratifiedKFold(5, shuffle=True, random_state=42).split(tablo, y_genel.fillna(0)))
    r = random.Random(42)

    satir, ayrik = [], []
    for ad_s, yorumlar in surum.items():
        metin = yorumlar.map(" ".join)
        for egitim, sinav in katlar:
            modeller = {}
            for ad, y in hedef.items():
                b = y.iloc[egitim].notna().to_numpy()
                modeller[ad] = ilk_model.model_kur().fit(metin.iloc[egitim][b], y.iloc[egitim][b].astype(int))
            for i in sinav:
                oid = tablo.at[i, "oyun_id"]
                p, renk, g = deney30.puanla(modeller, oid, yorumlar.iat[i], karne, magaza.get(oid))
                satir.append({"surum": ad_s, "oyun_id": oid, "puan": p, "renk": renk, "genel": g})
                if ad_s == "tam400" and len(yorumlar.iat[i]) >= 400:
                    for _ in range(TEKRAR):              # 200'de kararlılık: iki ayrık yarım
                        k = r.sample(yorumlar.iat[i], 400)
                        a = deney30.puanla(modeller, oid, k[:200], karne, magaza.get(oid))
                        b2 = deney30.puanla(modeller, oid, k[200:], karne, magaza.get(oid))
                        ayrik.append({"oyun_id": oid, "renk_a": a[1], "renk_b": b2[1], "fark": abs(a[0] - b2[0])})
        print(f"{ad_s} bitti", flush=True)

    df = pd.DataFrame(satir).merge(pd.DataFrame({"oyun_id": tablo.oyun_id, "karanlik": y_genel}), on="oyun_id")
    df.to_csv(VERI / "sonuclar_yorum_400.csv", index=False, encoding="utf-8")
    b = df[df.karanlik.notna()]
    print("\nSürüm    kural AUC  model AUC  | renk: oyun sayısı (karanlık payı)")
    for ad_s, g in b.groupby("surum"):
        renk = " ".join(f"{rn}: {int((g.renk == rn).sum())} (%{100 * g.karanlik[g.renk == rn].mean():.0f})"
                        for rn in RENKLER)
        print(f"{ad_s:<8} {roc_auc_score(g.karanlik, g.puan):.3f}      {roc_auc_score(g.karanlik, g.genel):.3f}"
              f"      | {renk}")
    p = df.pivot(index="oyun_id", columns="surum", values="renk")
    print(f"\n200 -> 400 renk değişen oyun: {(p.ilk200 != p.tam400).sum()} / {len(p)}")
    print(pd.crosstab(p.ilk200, p.tam400).reindex(index=RENKLER, columns=RENKLER).to_string())

    ay = pd.DataFrame(ayrik)
    zit = ay[["renk_a", "renk_b"]].apply(set, axis=1).map(lambda s: s == {"yesil", "kirmizi"})
    print(f"\nKararlılık, 200 yorum (iki ayrık örnek, {ay.oyun_id.nunique()} oyun x {TEKRAR}):"
          f" renk aynı %{100 * (ay.renk_a == ay.renk_b).mean():.0f} | yeşil<->kırmızı %{100 * zit.mean():.1f}"
          f" | puan 3+ değişen %{100 * (ay.fark >= 3).mean():.0f}")


if __name__ == "__main__":
    main()
