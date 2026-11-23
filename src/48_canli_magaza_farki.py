"""Adım 48: Canlı demo App Store sinyallerini okumuyor; bu kartı ne kadar değiştiriyor?

Kart sayfası: yorumlar + Google Play + App Store ("Loot Boxes" beyanı, reklam kaldırma ürünleri).
Canlı demo:   yorumlar + Google Play (App Store'a istek atılmaz).
Deney: 485 geliştirme kartında App Store kaynaklı mağaza kanıtları çıkarılır; puan ve renk aynı kurallarla
yeniden hesaplanır (sarı + model kırmızı -> kırmızı dahil). Yorumlar aynı kaldığı için fark yalnızca bu girdiden gelir.
Kullanım:  python src/48_canli_magaza_farki.py
"""

import importlib
import json
import sys

import pandas as pd
from sklearn.metrics import roc_auc_score

from ortak import VERI

kural = importlib.import_module("18_kural_karti")
RENKLER = ["yesil", "sari", "kirmizi"]


def renk(puan, model_renk):
    r = kural.kural_rengi(puan)
    return "kirmizi" if r == "sari" and model_renk == "kirmizi" else r


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    skor = pd.read_csv(VERI / "risk_skorlari.csv", dtype={"oyun_id": str}).set_index("oyun_id")
    satir = []
    for k in map(json.loads, open(VERI / "kartlar.jsonl", encoding="utf-8")):
        canli = {**k, "magaza_kanit": [m for m in k["magaza_kanit"] if not m["kanit"].startswith("App Store")]}
        puan = sum(kural.AGIRLIK[t] for t in kural.tespit_edilenler(canli))
        satir.append({"oyun_id": k["oyun_id"], "ad": k["ad"], "karanlik": skor.at[k["oyun_id"], "genel_gercek"],
                      "puan_tam": k["puan"], "puan_canli": puan, "renk_tam": k["renk"], "renk_canli": renk(puan, k["model_renk"])})
    d = pd.DataFrame(satir)
    b = d[d.karanlik.notna()]
    print(f"{len(d)} kart, karanlık etiketi belli {len(b)}")
    print(f"Puanı düşen kart: {int((d.puan_canli < d.puan_tam).sum())} (%{100 * (d.puan_canli < d.puan_tam).mean():.0f})")
    deg = d[d.renk_tam != d.renk_canli]
    print(f"Rengi değişen kart: {len(deg)} (%{100 * len(deg) / len(d):.0f})")
    print(pd.crosstab(d.renk_tam, d.renk_canli).reindex(index=RENKLER, columns=RENKLER).fillna(0).astype(int).to_string())
    for ad, p, r in (("Kart sayfası", "puan_tam", "renk_tam"), ("Canlı girdisi", "puan_canli", "renk_canli")):
        pay = " / ".join(f"{c} {int((b[r] == c).sum())} (%{100 * b.karanlik[b[r] == c].mean():.0f} karanlık)" for c in RENKLER)
        print(f"{ad}: puan AUC {roc_auc_score(b.karanlik, b[p]):.3f} | {pay}")
    e = deg[deg.karanlik.notna()]
    print(f"Rengi değişen ve etiketi belli {len(e)} oyunun karanlık payı: %{100 * e.karanlik.mean():.0f}")
    d.to_csv(VERI / "sonuclar_canli_magaza.csv", index=False, encoding="utf-8")


if __name__ == "__main__":
    main()
