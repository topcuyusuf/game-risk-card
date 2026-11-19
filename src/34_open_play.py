"""Adım 34: Open Play verisinden oyun başına 'sorunlu oynama' göstergesi (dış etiket denemesi).

Kaynak: Ballou ve ark. (2026), Open Play, Zenodo 10.5281/zenodo.23419571, CC0 + kimlik tespiti yasağı.
Veri: data/dis_kaynak/open_play/open-play.zip (yeniden yayımlanmaz; yalnızca oyun bazında toplamlar).

Kişi düzeyi:
  - GDT (Gaming Disorder Test, 4 soru, 1 = Never … 5 = Very often): kişinin tüm anketlerindeki ortalama.
  - Kişi -> oyun bağlantısı iki yoldan:
      a) Günlük anket 'en son oynadığın oyun' (tüm platformlar, mobil dahil, kendi beyanı)
      b) Steam ve Nintendo kayıtları (gerçek oynama dakikası)
Oyun düzeyi (en az MIN_KISI farklı oyuncu): oyuncularının ortalama GDT puanı, yüksek GDT'li oyuncu payı,
Steam/Nintendo'da kişi başı haftalık oynama süresi.
DİKKAT: bu bir OYUNCU ölçüsüdür; sorunlu oynayanlar belli oyunları seçiyor olabilir (seçim etkisi).
Kullanım:  python src/34_open_play.py
"""

import csv
import importlib
import io
import re
import sys
import zipfile

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score

from ortak import VERI

risk = importlib.import_module("14_risk_skoru")

ZIP = VERI / "dis_kaynak" / "open_play" / "open-play.zip"
ON = "digital-wellbeing-open-play-fdbf486/data/clean/"
GDT = {"never": 1, "rarely": 2, "sometimes": 3, "often": 4, "very often": 5}
MIN_KISI = 5
YUKSEK_GDT = 3.0          # 4 sorunun ortalaması 'Sometimes' ve üstü


def oku(z, ad):
    return pd.read_csv(io.BytesIO(z.read(ON + ad)), compression="gzip", low_memory=False)


def sade(a):
    """Eşleştirme için ad: küçük harf, alt başlık ve ™/® atılır, sadece harf+rakam."""
    a = str(a).lower().replace("™", "").replace("®", "")
    a = re.split(r"[:–—(]| - ", a)[0]
    return re.sub(r"[^a-z0-9]", "", a)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    z = zipfile.ZipFile(ZIP)

    # 1) Kişi GDT puanı
    b = oku(z, "survey_biweekly.csv.gz")
    for c in ["gdt_1", "gdt_2", "gdt_3", "gdt_4"]:
        b[c] = b[c].astype(str).str.strip().str.lower().map(GDT)
    b["gdt"] = b[["gdt_1", "gdt_2", "gdt_3", "gdt_4"]].mean(axis=1)
    kisi = b.groupby("pid")["gdt"].mean().dropna()
    print(f"GDT puanı olan kişi: {len(kisi)} | ortalama {kisi.mean():.2f} | yüksek (>= {YUKSEK_GDT}) %{100 * (kisi >= YUKSEK_GDT).mean():.0f}")

    # 2) Kişi -> oyun bağlantıları (her kişi bir oyunda bir kez sayılır)
    gun = oku(z, "survey_daily.csv.gz")[["pid", "most_recent_game", "most_recent_game_plat"]].dropna(subset=["most_recent_game"])
    gun["anahtar"] = gun.most_recent_game.map(sade)
    gun["mobil"] = gun.most_recent_game_plat.astype(str).str.contains("iOS|Android", case=False)
    st = oku(z, "steam.csv.gz")[["pid", "title_id", "minutes", "date"]]
    ni = oku(z, "nintendo.csv.gz")
    ni = ni.rename(columns={c: "minutes" for c in ni.columns if c.startswith("duration")})[["pid", "title_id", "minutes"]] \
        if "title_id" in ni else pd.DataFrame(columns=["pid", "title_id", "minutes"])
    tele = pd.concat([st[["pid", "title_id", "minutes"]], ni], ignore_index=True)
    tele["anahtar"] = tele.title_id.map(sade)
    gun_bag = gun.groupby(["anahtar", "pid"]).agg(kayit=("pid", "size"), mobil=("mobil", "any")).reset_index()
    tel_bag = tele.groupby(["anahtar", "pid"]).minutes.sum().reset_index()
    bag = pd.concat([gun_bag[["anahtar", "pid"]], tel_bag[["anahtar", "pid"]]]).drop_duplicates()
    bag = bag[bag.pid.isin(kisi.index) & (bag.anahtar != "")]
    bag["gdt"] = bag.pid.map(kisi)

    # Steam'de kişi başı haftalık dakika (kayıt süresine göre)
    gunler = st.groupby("pid").date.nunique().clip(lower=7)
    tel_bag["haftalik_dk"] = tel_bag.minutes / tel_bag.pid.map(gunler).fillna(7) * 7

    oyun = bag.groupby("anahtar").agg(kisi=("pid", "nunique"), ort_gdt=("gdt", "mean"),
                                      yuksek_pay=("gdt", lambda g: (g >= YUKSEK_GDT).mean()))
    oyun["mobil_beyan"] = gun_bag.groupby("anahtar").mobil.any()
    oyun["haftalik_dk"] = tel_bag.groupby("anahtar").haftalik_dk.median()
    oyun = oyun[oyun.kisi >= MIN_KISI].sort_values("ort_gdt", ascending=False)
    print(f"En az {MIN_KISI} oyunculu oyun: {len(oyun)} (mobilde beyan edilen: {int(oyun.mobil_beyan.fillna(False).sum())})")

    # 3) Bizim oyunlarla eşleştirme (darkpattern.games adları)
    with open(VERI / "oyun_linkleri.csv", encoding="utf-8", newline="") as f:
        ad = {s["oyun_id"]: s["ad"] for s in csv.DictReader(f)}
    tablo = pd.read_pickle(VERI / "oyun_tablosu.pkl")
    tablo["oyun_id"] = tablo.oyun_id.astype(str)
    gelistirme = set(tablo.oyun_id)
    test = pd.read_csv(VERI / "test_ios" / "sonuclar.csv", dtype={"oyun_id": str}).set_index("oyun_id")
    kural = pd.read_csv(VERI / "kural_puanlari.csv", dtype={"oyun_id": str}).set_index("oyun_id")
    skor = pd.read_csv(VERI / "risk_skorlari.csv", dtype={"oyun_id": str}).set_index("oyun_id")
    satir = []
    for oid, a in ad.items():
        k = sade(a)
        if k not in oyun.index:
            continue
        if oid in gelistirme:
            r = {"grup": "gelistirme", "kart": kural.at[oid, "kart_renk"], "puan": kural.at[oid, "puan"],
                 "model": skor.at[oid, "genel_olas"], "karanlik": kural.at[oid, "karanlik"]}
        elif oid in test.index:
            r = {"grup": "test", "kart": test.at[oid, "renk"], "puan": test.at[oid, "puan"],
                 "model": test.at[oid, "genel_olas"], "karanlik": test.at[oid, "karanlik"]}
        else:
            continue
        satir.append({"oyun_id": oid, "ad": a, **r, **oyun.loc[k].to_dict()})
    e = pd.DataFrame(satir).drop_duplicates("oyun_id")
    e.to_csv(VERI / "sonuclar_open_play.csv", index=False, encoding="utf-8")
    oyun.to_csv(VERI / "dis_kaynak" / "open_play" / "oyun_bazinda.csv", encoding="utf-8")
    print(f"Bizim kartı olan oyunlarla eşleşen: {len(e)} (geliştirme {int((e.grup == 'gelistirme').sum())}, test {int((e.grup == 'test').sum())})\n")
    if e.empty:
        return

    pd.set_option("display.width", 200)
    print(e.sort_values("ort_gdt", ascending=False)[["ad", "grup", "kisi", "ort_gdt", "yuksek_pay", "haftalik_dk", "kart", "puan", "model", "karanlik"]]
          .to_string(index=False, float_format=lambda v: f"{v:.2f}"))

    # 4) Kart ve model, oyuncuların sorunlu oynama puanıyla ilişkili mi?
    print("\nSıra ilişkisi (Spearman) — oyuncuların ortalama GDT puanı ile:")
    for c in ["puan", "model", "karanlik"]:
        x = e[[c, "ort_gdt"]].dropna()
        rho, p = spearmanr(x[c], x.ort_gdt)
        print(f"  {c:<9} n={len(x):<3} rho={rho:+.2f} (p={p:.2f})")
    print("Kart rengine göre ortalama GDT:")
    print(e.groupby("kart").agg(oyun=("ort_gdt", "size"), ort_gdt=("ort_gdt", "mean"), yuksek_pay=("yuksek_pay", "mean"))
          .reindex(["yesil", "sari", "kirmizi"]).to_string(float_format=lambda v: f"{v:.2f}"))
    tum = oyun.ort_gdt
    print(f"\nKarşılaştırma: tüm {len(tum)} oyunun ortalama GDT'si {tum.mean():.2f} (en düşük {tum.min():.2f}, en yüksek {tum.max():.2f})")


if __name__ == "__main__":
    main()
