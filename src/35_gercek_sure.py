"""Adım 35: Kart GERÇEK oynama süresini öngörüyor mu? (Open Play, Steam kayıtları)

Soru: kartın kırmızı dediği oyunlara oyuncular gerçekten daha çok zaman ayırıyor mu?
Kişi etkisini ayıklamak için her oyun, AYNI kişinin oynadığı diğer oyunlarla karşılaştırılır:
  göreli süre = log(kişinin bu oyundaki dakikası) - log(kişinin tüm oyunlarındaki ortalama dakikası)
  oyun değeri = oyunu oynayanların göreli sürelerinin ortalaması (en az MIN_KISI kişi)
  kat         = exp(oyun değeri)   (1 = kişinin ortalaması, 2 = iki katı)
Belirsizlik: oyunlar üzerinden bootstrap (2000 tekrar).
Kaynak: Ballou ve ark. (2026), Open Play (CC0 + kimlik tespiti yasağı). Yalnızca oyun bazında toplamlar.
Sınır: Steam (bilgisayar), ABD/İngiltere, 18-40 yaş; mobil sürüm değil.
Çıktı: data/sonuclar_gercek_sure.csv
(Karttaki süre ölçeği ve Şekil 11, 38. adımda bu 44 oyun + 37. adımın yeni oyunlarıyla üretilir.)
Kullanım:  python src/35_gercek_sure.py
"""

import importlib
import io
import re
import sys
import zipfile

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from ortak import KOK, VERI

op = importlib.import_module("34_open_play")          # sade(), ZIP

MIN_KISI = 5
RENKLER = ["yesil", "sari", "kirmizi"]
RENK_KOD = {"yesil": "#2E7D4F", "sari": "#E0A526", "kirmizi": "#C2412D"}


def tam(a):
    """Alt başlık KORUNARAK sadeleştirilmiş ad (küçük harf, ™/® yok, yalnız harf+rakam)."""
    return re.sub(r"[^a-z0-9]", "", str(a).lower().replace("™", "").replace("®", ""))


# İlk sürümde eşleşme alt başlıksız ada (op.sade) göre yapılıyordu; bu, farklı oyunları birleştirdi
# (ör. Game of Thrones: Conquest <-> Kingsroad). Sıkı kuralda Steam başlığının TAM adı, mobil adın tam
# hâline ya da alt başlıksız hâline eşit olmalı. Kurala uyduğu hâlde farklı olan oyunlar elle atılır:
ELLE_RET = {"callofduty": "Call of Duty: Mobile ayrı bir oyun; Steam'deki PC serisi",
            "uno": "mobil UNO! (Mattel163) ile Steam UNO (Ubisoft) farklı oyunlar"}


def kisi_baslik():
    """Steam: kişi x başlık (tam ad) dakikaları ve kişinin tüm başlıklarındaki ortalama log dakikası."""
    z = zipfile.ZipFile(op.ZIP)
    st = pd.read_csv(io.BytesIO(z.read(op.ON + "steam.csv.gz")), compression="gzip",
                     usecols=["pid", "title_id", "minutes"])
    st["tam"] = st.title_id.map(tam)
    kp = st[(st.tam != "") & (st.minutes > 0)].groupby(["pid", "tam"]).minutes.sum().reset_index()
    kp["kisi_ort"] = kp.groupby("pid").minutes.transform(lambda m: np.log(m).mean())
    return kp


def sure_esle(kp, hedefler):
    """hedefler: kabul edilen Steam tam adları. Dönüş: (kişi sayısı, ortalama göreli log süre, başlıklar)."""
    x = kp[kp.tam.isin(set(hedefler) - {""})]
    if x.empty:
        return 0, np.nan, ""
    k = x.groupby("pid").agg(minutes=("minutes", "sum"), kisi_ort=("kisi_ort", "first"))
    return len(k), float((np.log(k.minutes) - k.kisi_ort).mean()), "; ".join(sorted(x.tam.unique()))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    kp = kisi_baslik()
    e = pd.read_csv(VERI / "sonuclar_open_play.csv", dtype={"oyun_id": str})
    e["anahtar"] = e.ad.map(op.sade)
    e = e.drop_duplicates("anahtar")
    e = e[~e.anahtar.isin(ELLE_RET)]
    e[["kisi", "log_rel", "steam_baslik"]] = [sure_esle(kp, {tam(a), op.sade(a)}) for a in e.ad]
    e = e.astype({"kisi": int, "log_rel": float})
    e = e[e.kisi >= MIN_KISI].copy()
    e["kat"] = np.exp(e.log_rel)
    e.to_csv(VERI / "sonuclar_gercek_sure.csv", index=False, encoding="utf-8")
    print(f"Sıkı eşleşme, en az {MIN_KISI} oyuncu: {len(e)} oyun "
          f"(geliştirme {int((e.grup == 'gelistirme').sum())}, test {int((e.grup == 'test').sum())})\n")

    # Renk başına ortalama kat + bootstrap güven aralığı
    r = np.random.default_rng(42)
    print(f"{'Kart':<9}{'oyun':>5}{'kat':>7}   %95 aralık")
    olcek, aralik = {}, {}
    for renk in RENKLER:
        v = e.loc[e.kart == renk, "log_rel"].to_numpy()
        b = [np.exp(r.choice(v, len(v)).mean()) for _ in range(2000)]
        olcek[renk], aralik[renk] = float(np.exp(v.mean())), np.percentile(b, [2.5, 97.5])
        print(f"{renk:<9}{len(v):>5}{olcek[renk]:>7.2f}   {aralik[renk][0]:.2f} – {aralik[renk][1]:.2f}")
    yk = e.loc[e.kart == "kirmizi", "log_rel"].to_numpy()
    yy = e.loc[e.kart == "yesil", "log_rel"].to_numpy()
    fark = [np.exp(r.choice(yk, len(yk)).mean() - r.choice(yy, len(yy)).mean()) for _ in range(2000)]
    oran = float(np.exp(yk.mean() - yy.mean()))
    print(f"\nKırmızı / yeşil: {oran:.2f} kat (%95 aralık {np.percentile(fark, 2.5):.2f} – {np.percentile(fark, 97.5):.2f})")
    for c in ["puan", "model"]:
        rho, p = spearmanr(e[c], e.log_rel)
        print(f"Sıra ilişkisi, {c:<5} ~ göreli süre: rho={rho:+.2f} (p={p:.3f}, n={len(e)})")
    for grup, x in e.groupby("grup"):
        rho, p = spearmanr(x.puan, x.log_rel)
        print(f"  yalnız {grup:<10} n={len(x):<3} rho={rho:+.2f} (p={p:.2f})")


def grafik(e, olcek, aralik):
    """Şekil 11: renk başına kat + her oyun bir nokta (38. adım 81 oyunla çağırır)."""
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 3.8))
    for i, renk in enumerate(RENKLER):
        a1.bar(i, olcek[renk], color=RENK_KOD[renk],
               yerr=[[olcek[renk] - aralik[renk][0]], [aralik[renk][1] - olcek[renk]]], capsize=6)
        a1.text(i, aralik[renk][1] + 0.05, f"n={int((e.kart == renk).sum())}", ha="center", fontsize=9)
    a1.axhline(1, color="#555", lw=1, ls="--")
    a1.set_ylim(0, max(v[1] for v in aralik.values()) + 0.3)
    a1.set_xticks(range(3), ["Green", "Yellow", "Red"])
    a1.set_ylabel("Playtime vs. same player's other games (×)")
    a1.set_title("Real playtime by card colour (Steam)")
    a2.scatter(e.puan + np.random.default_rng(1).uniform(-.2, .2, len(e)), e.kat,
               c=e.kart.map(RENK_KOD), s=25, alpha=.8)
    a2.set_yscale("log"); a2.axhline(1, color="#555", lw=1, ls="--")
    a2.set_yticks([0.25, 0.5, 1, 2, 4], ["0.25", "0.5", "1", "2", "4"]); a2.minorticks_off()
    a2.set_xlabel("Card trap score"); a2.set_ylabel("Playtime ratio (×, log scale)")
    a2.set_title("Each dot = one game")
    fig.tight_layout()
    fig.savefig(KOK / "cikti" / "grafikler" / "11_playtime.png", dpi=150)
    print("-> cikti/grafikler/11_playtime.png")


if __name__ == "__main__":
    main()
