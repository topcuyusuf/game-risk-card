"""Adım 46: Wait To Play ve Grinding kurallarına yeni ifadeler eklemek kartı iyileştiriyor mu?

Neden: Candy Crush Saga'da oyuncular Wait To Play (canlar) ve Grinding'e "var" demiş, ama yorumlar bunu kuralın
aradığı kelimelerle değil, "bonus lives", "stuck on this level for weeks", "can't pass without boosters" diye anlatıyor.
Kart 4 puanla sarı kalıyor (kırmızı 5).
Deney: kural ESKİ ve YENİ (eski + ek ifadeler) hâliyle; diğer her şey aynı.
  Geliştirme (485 oyun): kural AUC (tuzak etiketi), akran eşiği, tespit, kart puanı AUC (karanlık oyun), renk payları.
  Bağımsız test (347 iOS oyunu): akran eşiği ve 'göster' kararı GELİŞTİRMEDEN dondurulur; dondurulmuş kartta yalnızca
  bu iki tuzağın tespiti yeniden hesaplanır (42. adımdaki yol).
Karar ölçütü (önceden): hem geliştirmede hem testte kart puanı AUC'si düşmemeli ve tuzak kuralının AUC'si artmalı.
Kullanım:  python src/46_kural_genisletme.py
"""

import importlib
import json
import re
import sys
from collections import defaultdict

import pandas as pd
from sklearn.metrics import roc_auc_score

from ortak import VERI

kn = importlib.import_module("15_kanitlar")
km = importlib.import_module("16_kart")
kural = importlib.import_module("18_kural_karti")
t23 = importlib.import_module("23_bagimsiz_test")

EK = {
    30: r"\b(?:no|run out of|ran out of|refill(?:ed|ing|s)?|buy(?:ing)?|more|extra|free|bonus) lives\b"
        r"|\blives (?:to|are|run|take|regenerate|refill)|\bwait (?:a day|days|hours|until tomorrow)\b"
        r"|\bhearts? (?:to )?(?:refill|regenerate)",
    12: r"stuck (?:on|at) (?:the same |this |that |one |a )?(?:level|stage)"
        r"|same (?:level|stage) for (?:days|weeks|months|a week|a month)"
        r"|(?:impossible|hard|harder) to (?:pass|beat|win|complete) without (?:buying|paying|boosters?|spending)"
        r"|can'?t (?:pass|beat|win|complete) (?:a |the |this )?(?:level |stage )?without (?:buying|paying|spending|boosters?)",
}
ESKI = {t: kn.KURALLAR[t] for t in EK}
YENI = {t: re.compile(kn.SOZLUK[t] + "|" + EK[t], re.I) for t in EK}
RENKLER = ["yesil", "sari", "kirmizi"]


def pay(yorumlar, k):
    return sum(kn.olumlu_eslesme(k, m) is not None for m in yorumlar), len(yorumlar)


def renk(puan, model_renk):
    r = kural.kural_rengi(puan)
    return "kirmizi" if r == "sari" and model_renk == "kirmizi" else r


def degerlendir(ad, d, karne):
    """d: oyun başına puan_eski, puan_yeni, model_renk, karanlik. Çıktı satırları."""
    b = d[d.karanlik.notna()]
    for s in ("eski", "yeni"):
        b = b.assign(**{f"renk_{s}": [renk(p, m) for p, m in zip(b[f"puan_{s}"], b.model_renk)]})
    print(f"\n{ad}: {len(b)} oyun (karanlık etiketi belli)")
    for s in ("eski", "yeni"):
        r = b[f"renk_{s}"]
        payl = " / ".join(f"{c} {int((r == c).sum())} (%{100 * b.karanlik[r == c].mean():.0f} karanlık)" for c in RENKLER)
        print(f"  {s}: kart puanı AUC {roc_auc_score(b.karanlik, b[f'puan_{s}']):.3f} | {payl}")
    degisen = b[b.renk_eski != b.renk_yeni]
    print(f"  rengi değişen: {len(degisen)} oyun; bunların karanlık payı %{100 * degisen.karanlik.mean():.0f}"
          if len(degisen) else "  rengi değişen yok")
    print(pd.crosstab(b.renk_eski, b.renk_yeni).reindex(index=RENKLER, columns=RENKLER).fillna(0).astype(int).to_string())
    return b


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    tablo = pd.read_pickle(VERI / "oyun_tablosu.pkl").set_index("oyun_id")
    skor = pd.read_csv(VERI / "risk_skorlari.csv", dtype={"oyun_id": str}).set_index("oyun_id")
    kartlar = {k["oyun_id"]: k for k in map(json.loads, open(VERI / "kartlar.jsonl", encoding="utf-8"))}

    # --- Geliştirme: paylar, kural AUC, akran eşiği ---
    karne, oran = {}, {}
    print("Kural AUC (geliştirme, tuzak etiketi) ve akran eşiği:")
    for t in EK:
        for s, k in (("eski", ESKI[t]), ("yeni", YENI[t])):
            n = {o: pay(tablo.at[o, "yorumlar"], k) for o in tablo.index}
            oran[(t, s)] = pd.Series({o: e / max(top, 1) for o, (e, top) in n.items()})
            oran[(t, s, "n")] = pd.Series({o: e for o, (e, _) in n.items()})
            y = tablo[f"t{t}"].dropna().astype(int)
            o = oran[(t, s)].loc[y.index]
            auc = roc_auc_score(y, o)
            karne[(t, s)] = {"goster": auc >= km.KURAL_AUC,
                             "esik": max(float(o[y == 0].quantile(km.AKRAN_YUZDELIK)), 1 / 200)}
            tespit = (oran[(t, s, "n")] >= 3) & (oran[(t, s)] >= km.MIN_KAT * karne[(t, s)]["esik"])
            yy = y.astype(bool)
            kesin = (tespit.loc[y.index] & yy).sum() / max(tespit.loc[y.index].sum(), 1)
            duyar = (tespit.loc[y.index] & yy).sum() / max(yy.sum(), 1)
            print(f"  {kn.HEDEF_TUZAKLAR[t]:<15} {s}: AUC {auc:.3f} | eşik %{100 * karne[(t, s)]['esik']:.1f} | "
                  f"tespit {int(tespit.sum())} oyun, kesinlik %{100 * kesin:.0f}, duyarlılık %{100 * duyar:.0f}")

    def tespitler(o, s):
        return {t for t in EK if karne[(t, s)]["goster"] and oran[(t, s, "n")][o] >= 3
                and oran[(t, s)][o] >= km.MIN_KAT * karne[(t, s)]["esik"]}

    satir = []
    for o, k in kartlar.items():
        temel = kural.tespit_edilenler(k) - set(EK)
        eski_kendi = kural.tespit_edilenler(k) & set(EK)
        satir.append({"oyun_id": o, "model_renk": k["model_renk"], "karanlik": skor.at[o, "genel_gercek"],
                      "kontrol": eski_kendi == tespitler(o, "eski"),
                      "puan_eski": sum(kural.AGIRLIK[t] for t in temel | tespitler(o, "eski")),
                      "puan_yeni": sum(kural.AGIRLIK[t] for t in temel | tespitler(o, "yeni")), "ad": k["ad"]})
    d = pd.DataFrame(satir).set_index("oyun_id")
    print(f"\nKontrol: eski kuralla yeniden hesaplanan tespit kartla aynı: %{100 * d.kontrol.mean():.1f}")
    g = degerlendir("GELİŞTİRME", d, karne)
    print("  Candy Crush Saga:", g.loc[g.ad == "Candy Crush Saga", ["puan_eski", "puan_yeni", "renk_eski", "renk_yeni"]]
          .to_dict("records"))

    # --- Bağımsız test (iOS): eşikler geliştirmeden ---
    sonuc = pd.read_csv(t23.KLASOR / "sonuclar.csv", dtype={"oyun_id": str}).set_index("oyun_id")
    tk = {k["oyun_id"]: k for k in map(json.loads, open(t23.KLASOR / "kartlar.jsonl", encoding="utf-8"))}
    yorum = defaultdict(list)
    for s in open(t23.KLASOR / "yorumlar.jsonl", encoding="utf-8"):
        y = json.loads(s)
        if y.get("metin"):
            yorum[y["oyun_id"]].append(y["metin"])
    satir = []
    for o, r in sonuc.iterrows():
        k = tk[o]
        temel = kural.tespit_edilenler(k) - set(EK)
        if k.get("reklamsiz"):
            temel.discard(13)
        p = {}
        for s, kurallar in (("eski", ESKI), ("yeni", YENI)):
            ek = set()
            for t in EK:
                e, top = pay(yorum[o], kurallar[t])
                if karne[(t, s)]["goster"] and e >= 3 and e / max(top, 1) >= km.MIN_KAT * karne[(t, s)]["esik"]:
                    ek.add(t)
            p[s] = sum(kural.AGIRLIK[t] for t in temel | ek)
            p[f"t_{s}"] = ek
        satir.append({"oyun_id": o, "model_renk": k["model_renk"], "karanlik": r.karanlik,
                      "puan_eski": p["eski"], "puan_yeni": p["yeni"], "kayitli_puan": r.puan,
                      **{f"tespit{t}_{s}": t in p[f"t_{s}"] for t in EK for s in ("eski", "yeni")},
                      **{f"et{t}": r[f"t{t}"] for t in EK}})
    d2 = pd.DataFrame(satir).set_index("oyun_id")
    print(f"\nKontrol (test): eski kuralla puan kayıtlı kartla aynı: %{100 * (d2.puan_eski == d2.kayitli_puan).mean():.1f}")
    degerlendir("BAĞIMSIZ TEST (iOS)", d2, karne)
    print("  Tuzak bazında (test, etiketi belli oyunlar):")
    for t in EK:
        e = d2[d2[f"et{t}"].notna()]
        for s in ("eski", "yeni"):
            tes = e[f"tespit{t}_{s}"]
            kes = e.loc[tes, f"et{t}"].mean() if tes.any() else float("nan")
            duy = tes[e[f"et{t}"] == 1].mean()
            print(f"    {kn.HEDEF_TUZAKLAR[t]:<15} {s}: tespit {int(tes.sum())}, kesinlik %{100 * kes:.0f}, "
                  f"duyarlılık %{100 * duy:.0f}")
    d.to_csv(VERI / "sonuclar_kural_genisletme.csv", encoding="utf-8")


if __name__ == "__main__":
    main()
