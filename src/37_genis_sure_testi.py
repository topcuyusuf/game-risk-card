"""Adım 37: Dondurulmuş kart, darkpattern.games'te OLMAYAN oyunlarda gerçek süreyi öngörüyor mu?

36. adımda Open Play'deki Steam oyunlarının resmî Google Play sürümleri bulundu ve 200 yorum toplandı.
Bu oyunlar kartın eğitiminde ve 35. adımdaki 60 oyunda yok -> tamamen yeni bir test.
Her oyuna dondurulmuş sistemle (sistem.kart_uret) kart verilir; renk ve puan, Steam'deki
"aynı kişinin diğer oyunlarına göre" süreyle (log_rel) karşılaştırılır.
Mağaza bilgisi (kategori, reklam var mı) Google Play'den bir kez alınır, data/open_play_play/bilgi.jsonl'a yazılır.
Çıktı: data/sonuclar_genis_sure.csv
Kullanım:  python src/37_genis_sure_testi.py
"""

import importlib
import json
import sys
import time

import numpy as np
import pandas as pd
from google_play_scraper import app
from scipy.stats import spearmanr

import sistem as sistem_mod
from ortak import VERI

o36 = importlib.import_module("36_open_play_play")
o35 = importlib.import_module("35_gercek_sure")     # sıkı eşleşme: kisi_baslik(), sure_esle(), tam()

BILGI = o36.KLASOR / "bilgi.jsonl"
RENKLER = ["yesil", "sari", "kirmizi"]


def magaza_bilgisi(play_idler):
    """Kategori ve containsAds; önbellekli."""
    eski = {}
    if BILGI.exists():
        for s in open(BILGI, encoding="utf-8"):
            d = json.loads(s); eski[d["play_id"]] = d
    with open(BILGI, "a", encoding="utf-8") as f:
        for pid in play_idler:
            if pid in eski:
                continue
            b = app(pid, lang="en", country="us")
            d = {"play_id": pid, "kategoriler": [k["name"] for k in b.get("categories", []) if k.get("name")],
                 "reklam": b.get("containsAds"), "ucretsiz": b.get("free")}
            f.write(json.dumps(d, ensure_ascii=False) + "\n"); f.flush()
            eski[pid] = d
            time.sleep(o36.BEKLEME)
    return eski


def ozet(e, baslik):
    """Renk başına kat, kırmızı/yeşil (veya sarı/yeşil) ve sıra ilişkisi."""
    r = np.random.default_rng(42)
    print(f"\n== {baslik} (n={len(e)}) ==")
    print(f"{'Kart':<9}{'oyun':>5}{'kat':>7}   %95 aralık")
    for renk in RENKLER:
        v = e.loc[e.kart == renk, "log_rel"].to_numpy()
        if len(v) == 0:
            print(f"{renk:<9}{0:>5}"); continue
        b = [np.exp(r.choice(v, len(v)).mean()) for _ in range(2000)]
        lo, hi = np.percentile(b, [2.5, 97.5])
        print(f"{renk:<9}{len(v):>5}{np.exp(v.mean()):>7.2f}   {lo:.2f} – {hi:.2f}")
    yy = e.loc[e.kart == "yesil", "log_rel"].to_numpy()
    yk = e.loc[e.kart != "yesil", "log_rel"].to_numpy()
    if len(yy) and len(yk):
        f = [np.exp(r.choice(yk, len(yk)).mean() - r.choice(yy, len(yy)).mean()) for _ in range(2000)]
        print(f"Sarı+kırmızı / yeşil: {np.exp(yk.mean() - yy.mean()):.2f} kat "
              f"(%95 {np.percentile(f, 2.5):.2f} – {np.percentile(f, 97.5):.2f})")
    for c in ["puan", "model"]:
        rho, p = spearmanr(e[c], e.log_rel)
        print(f"Sıra ilişkisi {c:<5} ~ süre: rho={rho:+.2f} (p={p:.3f})")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sistem = sistem_mod.sistemi_yukle()
    es = pd.read_csv(o36.ESLESME)
    es = es[(es.sonuc == "kabul") & ~es.play_id.isin(o36.ELLE_RET)].drop_duplicates("play_id")
    yor = pd.read_json(o36.YORUMLAR, lines=True)
    kp = o35.kisi_baslik()
    bilgi = magaza_bilgisi(es.play_id)

    satir = []
    for _, r in es.iterrows():
        y = yor[yor.play_id == r.play_id][["metin", "yildiz", "faydali_oy"]].to_dict("records")
        if len(y) < 20:
            continue
        b = bilgi[r.play_id]
        magaza = {"ios_var": False, "ios_etiketler": [], "urunler": [],
                  "play_kategoriler": b["kategoriler"], "play_reklam": b["reklam"]}
        kisi, log_rel, _ = o35.sure_esle(kp, {o35.tam(r.steam_ad), o35.tam(r.play_ad)})   # yalnız o Steam başlığı
        if kisi < o35.MIN_KISI:
            continue
        k = sistem_mod.kart_uret(sistem, r.play_id, r.play_ad, y, "", magaza)
        satir.append({"anahtar": r.anahtar, "steam_ad": r.steam_ad, "play_ad": r.play_ad, "tur": r.tur,
                      "ucretsiz": b["ucretsiz"], "yorum": len(y), "kart": k["renk"], "puan": k["puan"],
                      "model": k["genel_olas"], "kisi": kisi, "log_rel": log_rel})
    e = pd.DataFrame(satir)
    e["kat"] = np.exp(e.log_rel)
    e.to_csv(VERI / "sonuclar_genis_sure.csv", index=False, encoding="utf-8")
    pd.set_option("display.width", 200)
    print(e.sort_values("puan")[["steam_ad", "ucretsiz", "kart", "puan", "model", "kisi", "kat"]]
          .to_string(index=False, float_format="%.2f"))
    print("\nRenk dağılımı:", e.kart.value_counts().to_dict(), "| ücretsiz:", int(e.ucretsiz.sum()))

    ozet(e, "YENİ oyunlar (darkpattern.games'te yok)")

    eski = pd.read_csv(VERI / "sonuclar_gercek_sure.csv")[["anahtar", "kart", "puan", "model", "log_rel"]]
    birlesik = pd.concat([eski, e[["anahtar", "kart", "puan", "model", "log_rel"]]]).drop_duplicates("anahtar")
    ozet(birlesik, "35. adımdaki 60 oyun + yeni oyunlar")


if __name__ == "__main__":
    main()
