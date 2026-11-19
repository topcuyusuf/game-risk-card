"""Adım 42: Türkçe kurallar kartı iyileştiriyor mu? Bağımsız test (347 iOS oyunu).

41. adımda geliştirme setinde 'İngilizce VEYA Türkçe kural' kart puanını iyileştirdi (AUC 0.750 -> 0.785).
Bu adımda aynı fikir, hiç dokunulmamış iOS test oyunlarında sınanır:
  - Türkçe App Store yorumları toplanır (Apple RSS, country=tr; en fazla 4 x 50; yazar adı alınmaz).
  - Türkçe kural karnesi (hangi kural gösterilir, akran eşiği) YALNIZCA 485 geliştirme oyunundan hesaplanır, dondurulur.
  - Her test oyununun dondurulmuş İngilizce kartı (23. adım) alınır; Türkçe kuralın bulduğu tuzaklar eklenir,
    puan ve renk aynı kurallarla yeniden hesaplanır (sarı + model kırmızı -> kırmızı dahil).
Kullanım:  python src/42_turkce_ios_testi.py topla
           python src/42_turkce_ios_testi.py degerlendir
"""

import argparse
import importlib
import json
import sys
import time
from collections import defaultdict

import pandas as pd
import requests
from sklearn.metrics import roc_auc_score

from ortak import HEDEF_TUZAKLAR, VERI

t23 = importlib.import_module("23_bagimsiz_test")
t41 = importlib.import_module("41_turkce_kurallar")
o40 = importlib.import_module("40_turkce_model")
kart_mod = importlib.import_module("16_kart")
kural = importlib.import_module("18_kural_karti")

YORUMLAR_TR, DURUM_TR = t23.KLASOR / "yorumlar_tr.jsonl", t23.KLASOR / "durum_tr.csv"
MIN_TR = 20          # Türkçe kuralın devreye girmesi için en az bu kadar Türkçe yorum


def sayfa_tr(ios_id, sayfa):
    k = "https://itunes.apple.com/tr/rss/customerreviews"
    for url in [f"{k}/page={sayfa}/id={ios_id}/sortby=mosthelpful/json", f"{k}/page={sayfa}/id={ios_id}/json"]:
        r = requests.get(url, headers=t23.magaza_mod.BASLIK, timeout=30)
        time.sleep(t23.BEKLEME)
        g = r.json().get("feed", {}).get("entry", []) if r.status_code == 200 else []
        g = [g] if isinstance(g, dict) else g
        if g:
            return g
    return []


def topla():
    oyunlar = [json.loads(s) for s in open(t23.OYUNLAR, encoding="utf-8")]
    bitmis = set(pd.read_csv(DURUM_TR, dtype=str).oyun_id) if DURUM_TR.exists() else set()
    yapilacak = [o for o in oyunlar if o["oyun_id"] not in bitmis]
    print(f"Test oyunu: {len(oyunlar)} | bitmiş: {len(bitmis)} | şimdi: {len(yapilacak)}", flush=True)
    yeni = not DURUM_TR.exists()
    with open(YORUMLAR_TR, "a", encoding="utf-8") as f_y, open(DURUM_TR, "a", encoding="utf-8") as f_d:
        if yeni:
            f_d.write("oyun_id,yorum_sayisi\n")
        for sira, o in enumerate(yapilacak, 1):
            gorulen = set()
            try:
                for s in range(1, t23.SAYFA + 1):
                    g = sayfa_tr(o["ios_id"], s)
                    for e in g:
                        kimlik = e.get("id", {}).get("label")
                        if "content" in e and kimlik not in gorulen:
                            gorulen.add(kimlik)
                            f_y.write(json.dumps({"oyun_id": o["oyun_id"], "metin": e["content"]["label"],
                                                  "yildiz": int(e["im:rating"]["label"]),
                                                  "faydali_oy": int(e["im:voteSum"]["label"])}, ensure_ascii=False) + "\n")
                    if len(g) < 50:
                        break
            except Exception as hata:
                print(f"  ! {o['ad']}: {str(hata)[:80]}", flush=True)
                continue
            f_d.write(f"{o['oyun_id']},{len(gorulen)}\n"); f_y.flush(); f_d.flush()
            if sira % 25 == 0:
                print(f"[{sira}/{len(yapilacak)}] {o['ad']}: {len(gorulen)}", flush=True)
    print("bitti", flush=True)


def turkce_karne():
    """Geliştirme setinden (485 oyun, Play Türkçe yorumları) dondurulmuş Türkçe kural karnesi."""
    tablo = pd.read_pickle(VERI / "oyun_tablosu.pkl").reset_index(drop=True)
    tr_g = pd.read_json(o40.o39.YORUMLAR, lines=True, dtype={"oyun_id": str}).groupby("oyun_id").metin.agg(list)
    tr_g = tr_g[tr_g.map(len) >= o40.MIN_YORUM]
    tablo = tablo[tablo.oyun_id.isin(tr_g.index)].reset_index(drop=True)
    pay, _ = t41.paylar({i: [t41.normal(m) for m in tr_g[o]] for i, o in tablo.oyun_id.items()},
                        t41.KURALLAR_TR, t41.olumlu_tr)
    karne = {}
    for t in kural.AGIRLIK:
        y = tablo[f"t{t}"].dropna().astype(int)
        auc = roc_auc_score(y, pay.loc[y.index, f"t{t}"])
        karne[t] = {"goster": auc >= kart_mod.KURAL_AUC and t not in kart_mod.MODEL_TUZAKLARI, "auc": auc,
                    "akran_esik": max(float(pay.loc[y.index[y == 0], f"t{t}"].quantile(kart_mod.AKRAN_YUZDELIK)), 1 / 200)}
    return karne


def renk_yeniden(puan, model_renk):
    r = kural.kural_rengi(puan)
    return "kirmizi" if r == "sari" and model_renk == "kirmizi" else r


def degerlendir():
    karne = turkce_karne()
    print("Türkçe kural karnesi (geliştirme setinden):")
    for t, k in karne.items():
        print(f"  {HEDEF_TUZAKLAR[t]:<28} AUC {k['auc']:.3f}  {'göster' if k['goster'] else 'gizle'}")

    sonuc = pd.read_csv(t23.KLASOR / "sonuclar.csv", dtype={"oyun_id": str}).set_index("oyun_id")
    kartlar = {k["oyun_id"]: k for k in map(json.loads, open(t23.KLASOR / "kartlar.jsonl", encoding="utf-8"))}
    tr = defaultdict(list)
    for s in open(YORUMLAR_TR, encoding="utf-8"):
        y = json.loads(s); tr[y["oyun_id"]].append(t41.normal(y["metin"]))

    satir = []
    for oid, r in sonuc.iterrows():
        k = kartlar[oid]
        tespit = kural.tespit_edilenler(k)
        if k.get("reklamsiz"):
            tespit.discard(13)
        ek = set()
        if len(tr[oid]) >= MIN_TR:
            for t, kk in karne.items():
                n = sum(t41.olumlu_tr(t41.KURALLAR_TR[t], m) is not None for m in tr[oid])
                if kk["goster"] and n >= 3 and n / len(tr[oid]) >= kart_mod.MIN_KAT * kk["akran_esik"] \
                        and not (t == 13 and k.get("reklamsiz")):
                    ek.add(t)
        puan2 = sum(kural.AGIRLIK[t] for t in tespit | ek)
        satir.append({"oyun_id": oid, "tr_yorum": len(tr[oid]), "karanlik": r.karanlik, "puan": k["puan"],
                      "renk": k["renk"], "puan2": puan2, "renk2": renk_yeniden(puan2, k["model_renk"]),
                      "yeni_tuzak": len(ek - tespit)})
    d = pd.DataFrame(satir)
    d.to_csv(t23.KLASOR / "sonuclar_tr.csv", index=False, encoding="utf-8")
    kume = d[(d.tr_yorum >= MIN_TR) & d.karanlik.notna()]
    print(f"\nTest oyunu: {len(d)} | en az {MIN_TR} Türkçe yorumu olan (etiketi belli): {len(kume)}")
    print(f"Türkçe kuralın yeni tuzak eklediği oyun: {int((kume.yeni_tuzak > 0).sum())}")
    for ad, p, rk in [("Yalnız İngilizce (dondurulmuş kart)", "puan", "renk"), ("İngilizce + Türkçe kurallar", "puan2", "renk2")]:
        pay = " / ".join(f"%{100 * kume.loc[kume[rk] == c, 'karanlik'].mean():.0f} (n={int((kume[rk] == c).sum())})"
                         for c in ["yesil", "sari", "kirmizi"])
        print(f"{ad:<38} puan AUC {roc_auc_score(kume.karanlik, kume[p]):.3f} | karanlık payı yeşil/sarı/kırmızı: {pay}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser()
    p.add_argument("asama", choices=["topla", "degerlendir"])
    {"topla": topla, "degerlendir": degerlendir}[p.parse_args().asama]()
