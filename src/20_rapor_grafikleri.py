"""Adım 20: Ödev raporları için grafikler + hiperparametre (C) denemesi.

Çıktı: cikti/grafikler/*.png ve data/sonuclar_c_ayari.csv
Grafikler sadece özet sayılar içerir (ham oy verisi yok).
Kullanım:  python src/20_rapor_grafikleri.py
"""

import importlib
import json

import matplotlib
matplotlib.use("Agg")                      # Ekran olmadan dosyaya çiz
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch
from sklearn.base import clone
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, roc_auc_score, roc_curve
from sklearn.model_selection import KFold, StratifiedKFold, cross_val_predict

from ortak import HEDEF_TUZAKLAR, KOK, VERI

ilk_model = importlib.import_module("10_ilk_model")
risk = importlib.import_module("14_risk_skoru")
KLASOR = KOK / "cikti" / "grafikler"
KLASOR.mkdir(parents=True, exist_ok=True)
MAVI, TURUNCU, GRI, KOYU = "#2F5DA8", "#E07B28", "#B8B4AA", "#1D2433"
plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False,
                     "figure.dpi": 150})
SUTUN = [f"t{t}" for t in HEDEF_TUZAKLAR]


def kaydet(ad):
    plt.tight_layout()
    plt.savefig(KLASOR / ad, bbox_inches="tight")
    plt.close()
    print("  ->", ad)


def huni():
    asama = ["All games on site", "≥1 player vote", "Enough votes (14 traps)",
             "Found on Google Play", "Still live on Play", "≥1 clear label"]
    sayi = [31000, 2099, 994, 574, 497, 485]
    plt.figure(figsize=(8, 3.6))
    y = np.arange(len(asama))[::-1]
    plt.barh(y, sayi, color=[GRI] * 5 + [MAVI])
    plt.xscale("log")
    plt.yticks(y, asama)
    for yi, s in zip(y, sayi):
        plt.text(s * 1.1, yi, f"{s:,}", va="center")
    plt.xlabel("Number of games (log scale)")
    plt.title("Data funnel: from 31,000 games to 485")
    kaydet("01_funnel.png")


def etiket_sayilari(tablo):
    ad = [HEDEF_TUZAKLAR[int(c[1:])] for c in SUTUN]
    var = [(tablo[c] == 1).sum() for c in SUTUN]
    yok = [(tablo[c] == 0).sum() for c in SUTUN]
    bil = [tablo[c].isna().sum() for c in SUTUN]
    sira = np.argsort(var)
    y = np.arange(len(ad))
    plt.figure(figsize=(8, 5))
    plt.barh(y, np.array(var)[sira], color=MAVI, label="Yes (1)")
    plt.barh(y, np.array(yok)[sira], left=np.array(var)[sira], color=TURUNCU, label="No (0)")
    plt.barh(y, np.array(bil)[sira], left=np.array(var)[sira] + np.array(yok)[sira], color=GRI,
             label="Unknown")
    plt.yticks(y, np.array(ad)[sira])
    plt.xlabel("Games (n = 485)")
    plt.title("Labels per trap")
    plt.legend(loc="lower right", frameon=False)
    kaydet("02_label_counts.png")


def korelasyon(tablo):
    k = tablo[SUTUN].corr()
    kisa = [HEDEF_TUZAKLAR[int(c[1:])][:18] for c in SUTUN]
    plt.figure(figsize=(7.5, 6.3))
    plt.imshow(k, cmap="Blues", vmin=0, vmax=1)
    plt.xticks(range(14), kisa, rotation=60, ha="right", fontsize=8)
    plt.yticks(range(14), kisa, fontsize=8)
    plt.colorbar(label="Correlation")
    ort = k.where(~np.eye(14, dtype=bool)).stack().mean()
    plt.title(f"Trap labels are linked (mean correlation {ort:.2f})")
    kaydet("03_label_correlation.png")


def roc_ve_matris(tablo):
    veri = tablo[tablo["t13"].notna()].reset_index(drop=True)
    y = veri["t13"].astype(int).to_numpy()
    metin = veri["yorumlar"].map(" ".join)
    katlar = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    olas = cross_val_predict(ilk_model.model_kur(), metin, y, cv=katlar, method="predict_proba")[:, 1]
    fpr, tpr, _ = roc_curve(y, olas)
    auc = roc_auc_score(y, olas)
    isaret = veri["reklam_var"].to_numpy()
    plt.figure(figsize=(5.2, 4.6))
    plt.plot(fpr, tpr, color=MAVI, lw=2, label=f"Review model (AUC {auc:.2f})")
    plt.plot([0, 1], [0, 1], color=GRI, ls="--", label="Random (AUC 0.50)")
    fp = ((isaret == 1) & (y == 0)).sum() / (y == 0).sum()
    tp = ((isaret == 1) & (y == 1)).sum() / (y == 1).sum()
    plt.scatter([fp], [tp], color=TURUNCU, zorder=3, label="Play 'contains ads' flag")
    plt.xlabel("False positive rate")
    plt.ylabel("True positive rate")
    plt.title("Advertisements: ROC (5-fold, out-of-fold)")
    plt.legend(frameon=False, loc="lower right")
    kaydet("04_roc_ads.png")

    m = confusion_matrix(y, (olas >= 0.5).astype(int))
    plt.figure(figsize=(4.2, 3.6))
    plt.imshow(m, cmap="Blues")
    for i in range(2):
        for j in range(2):
            plt.text(j, i, m[i, j], ha="center", va="center",
                     color="white" if m[i, j] > m.max() / 2 else KOYU, fontsize=14)
    plt.xticks([0, 1], ["Pred: no", "Pred: yes"])
    plt.yticks([0, 1], ["True: no", "True: yes"])
    plt.title("Advertisements: confusion matrix")
    kaydet("05_confusion_ads.png")
    return auc, m


def genel_ozel():
    d = pd.read_csv(VERI / "sonuclar_genel_vs_ozel.csv").sort_values("AUC_ozel")
    y = np.arange(len(d))
    plt.figure(figsize=(8, 5))
    plt.barh(y - 0.2, d["AUC_ozel"], height=0.4, color=MAVI, label="Trap-specific model")
    plt.barh(y + 0.2, d["AUC_genel"], height=0.4, color=GRI, label="General 'dark game' model")
    plt.yticks(y, d["tuzak"])
    plt.xlim(0.5, 1)
    plt.xlabel("AUC (5-fold)")
    plt.title("Does each model learn its own trap?")
    plt.legend(frameon=False, loc="lower right")
    kaydet("06_specific_vs_general.png")


def kalibrasyon():
    s = pd.read_csv(VERI / "risk_skorlari.csv").dropna(subset=["genel_gercek"])
    s["dilim"] = pd.cut(s["genel_olas"], bins=np.arange(0, 1.01, 0.1))
    g = s.groupby("dilim", observed=True).agg(m=("genel_olas", "mean"), r=("genel_gercek", "mean"),
                                               n=("genel_gercek", "size"))
    plt.figure(figsize=(5, 4.4))
    plt.plot([0, 1], [0, 1], color=GRI, ls="--", label="Perfect calibration")
    plt.plot(g["m"], g["r"], "o-", color=MAVI, label="General model")
    plt.xlabel("Predicted probability")
    plt.ylabel("Observed share of dark games")
    plt.title("Calibration: the model is under-confident")
    plt.legend(frameon=False)
    kaydet("07_calibration.png")


def kural_puani():
    d = pd.read_csv(VERI / "kural_puanlari.csv")
    d["grup"] = d["puan"].clip(upper=6)
    g = d.groupby("grup").agg(r=("karanlik", "mean"), n=("puan", "size"))
    kural = importlib.import_module("18_kural_karti")       # eşikler tek yerden: 2 sarı, 5 kırmızı
    renk = ["#2E7D4F" if p < kural.SARI_PUAN else "#E0A526" if p < kural.KIRMIZI_PUAN else "#C2412D"
            for p in g.index]
    plt.figure(figsize=(6.5, 3.8))
    plt.bar(g.index, g["r"] * 100, color=renk)
    for p, r, n in zip(g.index, g["r"], g["n"]):
        plt.text(p, r * 100 + 2, f"n={n}", ha="center", fontsize=9)
    plt.xticks(g.index, ["0", "1", "2", "3", "4", "5", "6+"])
    plt.xlabel("Weighted rule score (green 0–1, yellow 2–4, red 5+)")
    plt.ylabel("Dark games (%)")
    plt.title("Higher rule score → more dark games")
    kaydet("08_rule_score.png")


def mimari():
    fig, ax = plt.subplots(figsize=(10, 4.2))
    ax.axis("off")
    kutu = [
        (0.0, 0.62, "darkpattern.games\nplayer votes", GRI),
        (0.0, 0.12, "Google Play\nreviews + store info", GRI),
        (0.22, 0.62, "Label builder\n(≥2 votes, majority)", "#DCE6F5"),
        (0.22, 0.12, "Text features\n(TF-IDF, 1–2 grams)", "#DCE6F5"),
        (0.46, 0.62, "Logistic regression\n(general + ads + pause)", "#DCE6F5"),
        (0.46, 0.12, "Keyword rules\n+ quote picker", "#DCE6F5"),
        (0.70, 0.37, "Risk card builder\n(weighted score,\nwarnings, quotes)", "#FBE3CF"),
        (0.88, 0.37, "Card page\n(HTML)", GRI),
    ]
    for x, y, t, c in kutu:
        ax.add_patch(FancyBboxPatch((x, y), 0.16, 0.26, boxstyle="round,pad=0.01", fc=c, ec=KOYU, lw=1))
        ax.text(x + 0.08, y + 0.13, t, ha="center", va="center", fontsize=9)
    oklar = [((0.16, 0.75), (0.22, 0.75)), ((0.16, 0.25), (0.22, 0.25)), ((0.38, 0.75), (0.46, 0.75)),
             ((0.38, 0.25), (0.46, 0.25)), ((0.30, 0.38), (0.54, 0.62)), ((0.62, 0.75), (0.70, 0.55)),
             ((0.62, 0.25), (0.70, 0.45)), ((0.86, 0.50), (0.88, 0.50))]
    for a, b in oklar:
        ax.annotate("", xy=b, xytext=a, arrowprops=dict(arrowstyle="->", color=KOYU))
    ax.set_xlim(-0.01, 1.05)
    ax.set_ylim(0, 1)
    ax.set_title("System architecture")
    kaydet("00_architecture.png")


def c_ayari(tablo):
    """C (düzenlileştirme) denemesi: aynı 5 kat, aynı TF-IDF, farklı C."""
    tablo = tablo.reset_index(drop=True)
    metin = tablo["yorumlar"].map(" ".join)
    hedef = {"General dark game": risk.genel_karanlik(tablo), "Advertisements": tablo["t13"],
             "Can't Pause or Save": tablo["t28"], "Daily Rewards": tablo["t11"]}
    C_DEGER = [0.1, 0.3, 1, 3, 10]
    olas = {(h, c): np.full(len(tablo), np.nan) for h in hedef for c in C_DEGER}
    for egitim, sinav in KFold(5, shuffle=True, random_state=42).split(tablo):
        tf = clone(ilk_model.model_kur()[0])
        X_eg, X_sn = tf.fit_transform(metin.iloc[egitim]), tf.transform(metin.iloc[sinav])
        for h, y in hedef.items():
            yy = y.iloc[egitim]
            b = yy.notna().to_numpy()
            for c in C_DEGER:
                m = LogisticRegression(C=c, class_weight="balanced", max_iter=3000)
                m.fit(X_eg[b], yy[b].astype(int))
                olas[(h, c)][sinav] = m.predict_proba(X_sn)[:, 1]
    satir = []
    for h, y in hedef.items():
        b = y.notna().to_numpy()
        for c in C_DEGER:
            satir.append({"hedef": h, "C": c, "AUC": roc_auc_score(y[b].astype(int), olas[(h, c)][b])})
    df = pd.DataFrame(satir)
    df.to_csv(VERI / "sonuclar_c_ayari.csv", index=False)
    print(df.pivot(index="hedef", columns="C", values="AUC").round(3).to_string())
    plt.figure(figsize=(6.5, 4))
    for (h, g), r in zip(df.groupby("hedef"), [MAVI, TURUNCU, KOYU, GRI]):
        plt.plot(g["C"], g["AUC"], "o-", color=r, label=h)
    plt.xscale("log")
    plt.xlabel("C (higher = less regularization)")
    plt.ylabel("AUC (5-fold)")
    plt.title("Hyperparameter check: regularization strength C")
    plt.legend(frameon=False, fontsize=9)
    kaydet("09_c_tuning.png")


def main():
    tablo = pd.read_pickle(VERI / "oyun_tablosu.pkl")
    print("Grafikler:")
    mimari()
    huni()
    etiket_sayilari(tablo)
    korelasyon(tablo)
    auc, m = roc_ve_matris(tablo)
    print(f"  Ads AUC {auc:.3f}, karışıklık matrisi {m.tolist()}")
    genel_ozel()
    kalibrasyon()
    kural_puani()
    print("C denemesi:")
    c_ayari(tablo)


if __name__ == "__main__":
    main()
