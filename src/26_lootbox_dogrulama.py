"""Adım 26: Variable Rewards tespitini DIŞ uzman etiketleriyle doğrulama (eğitimde kullanılmaz).

Kaynak: araştırmacıların oyunları oynayarak verdiği "loot box var/yok" etiketleri (OSF, açık veri):
  - Zendle ve ark. 2019, en çok kazandıran 100 iPhone + 100 Android oyunu   (osf.io/xnw2t)
  - Xiao ve ark. 2021, İngiltere en çok kazandıran iPhone oyunları         (osf.io/cx5rv)
Dosyalar data/dis_kaynak/ altında; yeniden yayımlanmaz, kaynak gösterilir.
Oyun adı SADECE eşleştirme için kullanılır (modele girdi değildir).
Loot box, Variable Rewards'ın bir alt türüdür: loot box varsa tuzak vardır, yoksa yine de olabilir.
Kullanım:  python src/26_lootbox_dogrulama.py
"""

import csv
import importlib
import json
import re
import sys

import pandas as pd
from sklearn.metrics import roc_auc_score

from ortak import VERI

kural = importlib.import_module("18_kural_karti")
K = VERI / "dis_kaynak"


def sade(a):
    """Eşleştirme için ad: alt başlık atılır, sadece harf ve rakam."""
    a = re.split(r"[:–—]| - ", str(a).lower())[0]
    return re.sub(r"[^a-z0-9]", "", a)


def lootbox_kayitlari():
    kayit = []
    dosya = K / "xnw2t__Loot Boxes Addiction - Full Prevalence Data August 2019 Final.xlsx"
    for sayfa in ["iPhone Games", "Android Games"]:
        d = pd.read_excel(dosya, sheet_name=sayfa, header=1)
        for _, r in d.iterrows():
            son = str(r.iloc[15]).strip().lower()          # "Final coding" sütunu
            if isinstance(r["Name"], str) and son in ("yes", "no"):
                kayit.append((r["Name"], int(son == "yes")))
    d = pd.read_csv(K / "cx5rv_ham" / "Raw Data and Analyses" / "UK LB Disclosure.csv")
    for _, r in d.iterrows():                               # 0 yok, 1 var, 3 sadece kullanıcı içeriği (= yok), 2 belirsiz
        if r["containslb"] in (0, 1, 3):
            kayit.append((r["name"], int(r["containslb"] == 1)))
    return kayit


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    with open(VERI / "oyun_linkleri.csv", encoding="utf-8", newline="") as f:
        ad_to = {}
        for s in csv.DictReader(f):
            ad_to.setdefault(sade(s["ad"]), []).append(s["oyun_id"])
    kart = {}
    for dosya in [VERI / "kartlar.jsonl", VERI / "test_ios" / "kartlar.jsonl"]:
        for s in open(dosya, encoding="utf-8"):
            k = json.loads(s)
            kart[str(k["oyun_id"])] = k

    etiket = {}
    for ad, v in lootbox_kayitlari():
        for i in ad_to.get(sade(ad), []):
            etiket.setdefault(i, []).append(v)
    d = pd.DataFrame([(i, round(sum(v) / len(v))) for i, v in etiket.items() if i in kart],
                     columns=["oyun_id", "lootbox"])
    d["tespit"] = [49 in kural.tespit_edilenler(kart[i]) for i in d.oyun_id]
    d["yorum"] = [any(int(t.get("tuzak_id", -1)) == 49 for t in kart[i].get("tespitler", [])) for i in d.oyun_id]
    d["magaza"] = [any(m["tuzak_id"] == 49 for m in kart[i].get("magaza_kanit", [])) for i in d.oyun_id]
    d["puan"] = [kart[i]["puan"] for i in d.oyun_id]
    d.to_csv(K / "lootbox_sonuc.csv", index=False, encoding="utf-8")

    print(f"Kartı olan eşleşen oyun: {len(d)} | uzmana göre loot box var: {d.lootbox.sum()} (taban {d.lootbox.mean():.2f})\n")
    print(f"{'Variable Rewards kaynağı':<26}{'tespit':>7}{'isabet':>8}{'yakalama':>10}")
    for ad, c in (("Kart (yorum + mağaza)", "tespit"), ("Sadece yorumlar", "yorum"), ("Sadece App Store beyanı", "magaza")):
        x = d[c]
        print(f"{ad:<26}{x.sum():>7}{d.lootbox[x].mean():>8.2f}{x[d.lootbox == 1].mean():>10.2f}")
    print(f"\nKart puanı AUC (loot box var mı): {roc_auc_score(d.lootbox, d.puan):.3f}")


if __name__ == "__main__":
    main()
