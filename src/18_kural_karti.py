"""Adım 18: Ağırlıklı kural kartı — renk, tespit edilen tuzakların ağırlıklı toplamından.

Ağırlıklar (mentör + ekran süresi önceliğinin birleşimi):
  3: Variable Rewards
  2: Advertisements, Wait To Play, Grinding
  1: Daily Rewards, FOMO, Guilds, Competition, Invested, Can't Pause or Save
Bir tuzak 'tespit' sayılır: kelime kuralı tespiti VEYA (reklam/durdurma için) model uyarısı.
Kullanım:  python src/18_kural_karti.py
"""

import json

import pandas as pd

from ortak import HEDEF_TUZAKLAR, VERI

AGIRLIK = {49: 3, 13: 2, 30: 2, 12: 2, 11: 1, 53: 1, 21: 1, 54: 1, 24: 1, 28: 1}
AD_ID = {ad: t for t, ad in HEDEF_TUZAKLAR.items()}
# Renk eşikleri: puan tablosuna bakılarak seçildi. Mağaza sinyalleri eklenince puanlar yükseldi;
# gerçek risk artık 5 puanda düzleşiyor (puan 4: %63 karanlık, puan 5: %78), bu yüzden kırmızı 5+.
SARI_PUAN = 2
KIRMIZI_PUAN = 5


def kural_rengi(puan):
    return "kirmizi" if puan >= KIRMIZI_PUAN else "sari" if puan >= SARI_PUAN else "yesil"
SUTUNLAR = [f"t{t}" for t in HEDEF_TUZAKLAR]


def tespit_edilenler(kart):
    """Kartta tespit edilen (ağırlığı olan) tuzak id'leri; her tuzak bir kez sayılır."""
    ids = {d["tuzak_id"] for d in kart["tespitler"]}
    ids |= {AD_ID[u["tuzak"]] for u in kart["uyarilar"]}     # reklam / durdurma modeli
    ids |= {m["tuzak_id"] for m in kart.get("magaza_kanit", [])}   # mağaza sinyalleri
    return {t for t in ids if t in AGIRLIK}


def main():
    kartlar = [json.loads(s) for s in open(VERI / "kartlar.jsonl", encoding="utf-8")]
    tablo = pd.read_pickle(VERI / "oyun_tablosu.pkl").set_index("oyun_id")
    skor = pd.read_csv(VERI / "risk_skorlari.csv", dtype={"oyun_id": str}).set_index("oyun_id")

    df = pd.DataFrame([{"oyun_id": k["oyun_id"], "model_renk": k["model_renk"],
                        "puan": sum(AGIRLIK[t] for t in tespit_edilenler(k))} for k in kartlar])
    df = df.set_index("oyun_id")
    df["karanlik"] = skor["genel_gercek"]
    # Gerçek ağırlıklı risk: oyuncu etiketlerinden, aynı ağırlıklarla (bilinenler üzerinden)
    agir = pd.Series({f"t{t}": a for t, a in AGIRLIK.items()})
    etiket = tablo[agir.index]
    df["gercek_agirlikli"] = (etiket * agir).sum(axis=1) / (etiket.notna() * agir).sum(axis=1)

    print(f"En yüksek olası puan: {sum(AGIRLIK.values())}\n")
    print("Kural puanı -> gerçek durum:")
    print(df.groupby("puan").agg(oyun=("karanlik", "size"), karanlik=("karanlik", "mean"),
                                 gercek_agirlikli=("gercek_agirlikli", "mean"))
          .to_string(float_format="%.2f"))
    print("\nKural puanı ile gerçek ağırlıklı risk arasındaki sıra ilişkisi:",
          round(df["puan"].corr(df["gercek_agirlikli"], method="spearman"), 2))
    print("Model puanı ile gerçek ağırlıklı risk arasındaki sıra ilişkisi:",
          round(skor["genel_olas"].reindex(df.index).corr(df["gercek_agirlikli"], method="spearman"), 2))
    df["kural_renk"] = df["puan"].map(kural_rengi)
    df.to_csv(VERI / "kural_puanlari.csv", encoding="utf-8")

    sira = ["yesil", "sari", "kirmizi"]
    for ad, sutun in (("MODEL rengi", "model_renk"), ("KURAL rengi", "kural_renk")):
        print(f"\n{ad}:")
        print(df.groupby(sutun).agg(oyun=("puan", "size"), karanlik=("karanlik", "mean"),
                                    gercek_agirlikli=("gercek_agirlikli", "mean"))
              .reindex(sira).to_string(float_format="%.2f"))
    print("\nModel rengi (satır) x Kural rengi (sütun):")
    print(pd.crosstab(df["model_renk"], df["kural_renk"]).reindex(index=sira, columns=sira).to_string())
    ayni = (df["model_renk"] == df["kural_renk"]).mean()
    zit = ((df["model_renk"] == "yesil") & (df["kural_renk"] == "kirmizi") |
           (df["model_renk"] == "kirmizi") & (df["kural_renk"] == "yesil")).sum()
    print(f"\nAynı renk: %{100 * ayni:.0f} | Zıt renk (yeşil-kırmızı): {zit} oyun")


if __name__ == "__main__":
    main()
