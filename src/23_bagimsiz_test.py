"""Adım 23: BAĞIMSIZ TEST — hiçbir kararda kullanılmamış, sadece iOS'ta olan oylu oyunlar.

Sistem (modeller, kurallar, eşikler, ağırlıklar) DONDURULMUŞ haliyle uygulanır; burada
hiçbir ayar yapılmaz. Girdi: App Store yorumları (Apple'ın herkese açık yorum akışı).
Not: bu oyunların Play kimliği yok -> Play kategorisi sinyali ('Competitive multiplayer') yok.
Kullanım:  python src/23_bagimsiz_test.py topla [--adet N]
           python src/23_bagimsiz_test.py degerlendir
"""

import argparse
import csv
import importlib
import json
import time
from collections import defaultdict

import pandas as pd
import requests
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score

import sistem as sistem_mod
from ortak import HEDEF_TUZAKLAR, VERI

etiket_mod = importlib.import_module("08_etiketler")
veri_seti = importlib.import_module("09_veri_seti")
kural = importlib.import_module("18_kural_karti")
magaza_mod = importlib.import_module("21_magaza_sinyalleri")

KLASOR = VERI / "test_ios"
DENEMELER, OYUNLAR, YORUMLAR = KLASOR / "denemeler.csv", KLASOR / "oyunlar.jsonl", KLASOR / "yorumlar.jsonl"
BEKLEME, SAYFA, MIN_YORUM = 4, 4, 50      # 4 sayfa x 50 = 200 yorum


def oylar_ve_adaylar():
    """Tüm oyunların oyları + aday listesi: iOS kimliği var, Play kimliği yok, yeterli oy var."""
    oy = defaultdict(dict)
    with open(VERI / "tuzak_oylari.csv", encoding="utf-8", newline="") as f:
        for s in csv.DictReader(f):
            oy[s["oyun_id"]][int(s["tuzak_id"])] = (int(s["var"]), int(s["yok"]))
    with open(VERI / "oyun_durum.csv", encoding="utf-8", newline="") as f:
        durum = list(csv.DictReader(f))
    aday = [(s["oyun_id"], s["ios_id"]) for s in durum if s["ios_id"] and not s["play_id"]
            and any(sum(oy[s["oyun_id"]].get(t, (0, 0))) >= 2 for t in HEDEF_TUZAKLAR)]
    return oy, aday


def _sayfa(ios_id, sayfa, puan_sayisi):
    """Bir yorum sayfası. Apple'ın akışı tutarsız: aynı sayfa bazen boş, bazen dolu döner.
    Puanı çok olan oyunda boş gelirse, farklı adres biçimleriyle bekleyerek yeniden dener."""
    k = "https://itunes.apple.com/us/rss/customerreviews"
    bicimler = [f"{k}/page={sayfa}/id={ios_id}/sortby=mosthelpful/json",
                f"{k}/page={sayfa}/id={ios_id}/json"]
    if sayfa == 1:
        bicimler.append(f"{k}/id={ios_id}/json")
    deneme_sayisi = 6 if puan_sayisi >= 100 else 1
    for deneme in range(deneme_sayisi):
        url = bicimler[deneme % len(bicimler)]
        r = requests.get(url, headers=magaza_mod.BASLIK, timeout=30)
        time.sleep(BEKLEME)
        girdi = r.json().get("feed", {}).get("entry", []) if r.status_code == 200 else []
        if isinstance(girdi, dict):
            girdi = [girdi]
        if girdi:
            return girdi
        time.sleep(5 * (deneme + 1))
    return []


def yorumlari_cek(ios_id, puan_sayisi=0):
    """Apple yorum akışı, sayfa başına 50 yorum (en fazla 4 sayfa). Yazar adı alınmaz.
    Aynı yorum farklı adres biçimlerinden iki kez gelebilir: yorum kimliğiyle tekilleştirilir."""
    sonuc, gorulen = [], set()
    for sayfa in range(1, SAYFA + 1):
        girdi = _sayfa(ios_id, sayfa, puan_sayisi)
        for g in girdi:
            kimlik = g.get("id", {}).get("label")
            if "content" not in g or kimlik in gorulen:
                continue
            gorulen.add(kimlik)
            sonuc.append({"metin": g["content"]["label"], "yildiz": int(g["im:rating"]["label"]),
                          "faydali_oy": int(g["im:voteSum"]["label"])})
        if len(girdi) < 50:
            break
    return sonuc


def topla(adet):
    KLASOR.mkdir(exist_ok=True)
    _, aday = oylar_ve_adaylar()
    bakilan = set()
    if DENEMELER.exists():
        with open(DENEMELER, encoding="utf-8", newline="") as f:
            bakilan = {s["oyun_id"] for s in csv.DictReader(f)}
    yapilacak = [a for a in aday if a[0] not in bakilan][:adet]
    print(f"{len(aday)} aday, {len(bakilan)} bakılmış, şimdi {len(yapilacak)}")
    yeni = not DENEMELER.exists()
    with open(DENEMELER, "a", encoding="utf-8", newline="") as f_d, \
         open(OYUNLAR, "a", encoding="utf-8") as f_o, open(YORUMLAR, "a", encoding="utf-8") as f_y:
        yaz = csv.writer(f_d)
        if yeni:
            yaz.writerow(["oyun_id", "ios_id", "sonuc"])
        for sira, (oyun_id, ios_id) in enumerate(yapilacak, 1):
            try:
                r = requests.get("https://itunes.apple.com/lookup", params={"id": ios_id, "country": "us"},
                                 headers=magaza_mod.BASLIK, timeout=30)
                time.sleep(BEKLEME)
                s = (r.json().get("results") or [None])[0]
                if not s:
                    sonuc = "kaldirilmis"
                elif s.get("primaryGenreName") != "Games" and "Games" not in s.get("genres", []):
                    sonuc = "oyun_degil"
                else:
                    yorum = yorumlari_cek(ios_id, s.get("userRatingCount") or 0)
                    if len(yorum) < MIN_YORUM:
                        sonuc = f"az_yorum_{len(yorum)}"
                    else:
                        urunler = magaza_mod.apple_urunler(s["trackViewUrl"])
                        time.sleep(BEKLEME)
                        f_o.write(json.dumps({
                            "oyun_id": oyun_id, "ios_id": ios_id, "ad": s.get("trackName"),
                            "aciklama": veri_seti.html_temizle(s.get("description")),
                            "magaza": {"ios_var": True, "ios_etiketler": s.get("advisories", []),
                                       "urunler": urunler, "play_kategoriler": []},
                        }, ensure_ascii=False) + "\n")
                        for y in yorum:
                            f_y.write(json.dumps({"oyun_id": oyun_id, **y}, ensure_ascii=False) + "\n")
                        sonuc = "kabul"
            except Exception as hata:
                sonuc = "hata"
                print("  !", str(hata)[:120])
            if sonuc != "hata":                      # hata olanlar tekrar denenir
                yaz.writerow([oyun_id, ios_id, sonuc])
            for f in (f_d, f_o, f_y):
                f.flush()
            print(f"[{sira}/{len(yapilacak)}] {oyun_id}: {sonuc}")


def degerlendir():
    oy, _ = oylar_ve_adaylar()
    oyunlar = [json.loads(s) for s in open(OYUNLAR, encoding="utf-8")]
    yorum = defaultdict(list)
    for s in open(YORUMLAR, encoding="utf-8"):
        y = json.loads(s)
        yorum[y["oyun_id"]].append(y)

    sistem = sistem_mod.sistemi_yukle()          # dondurulmuş sistem (485 oyunla eğitilmiş)
    satir, kartlar = [], {}
    for o in oyunlar:
        k = sistem_mod.kart_uret(sistem, o["oyun_id"], o["ad"], yorum[o["oyun_id"]], o["aciklama"], o["magaza"])
        kartlar[o["oyun_id"]] = k
        et = {t: etiket_mod.etiket(*oy[o["oyun_id"]].get(t, (0, 0))) for t in HEDEF_TUZAKLAR}
        bilinen = [v for v in et.values() if v is not None]
        ort = sum(bilinen) / len(bilinen) if bilinen else None
        agir = [(kural.AGIRLIK[t], et[t]) for t in kural.AGIRLIK if et[t] is not None]
        satir.append({"oyun_id": o["oyun_id"], "renk": k["renk"], "model_renk": k["model_renk"],
                      "puan": k["puan"], "genel_olas": k["genel_olas"],
                      "karanlik": None if ort is None or ort == 0.5 else float(ort > 0.5),
                      "gercek_agirlikli": sum(a * e for a, e in agir) / sum(a for a, _ in agir) if agir else None,
                      **{f"t{t}": et[t] for t in HEDEF_TUZAKLAR},
                      **{f"d{t}": t in kural.tespit_edilenler(k) for t in kural.AGIRLIK}})
    df = pd.DataFrame(satir).set_index("oyun_id")
    df.to_csv(KLASOR / "sonuclar.csv", encoding="utf-8")
    with open(KLASOR / "kartlar.jsonl", "w", encoding="utf-8") as f:
        for k in kartlar.values():
            f.write(json.dumps(k, ensure_ascii=False) + "\n")

    sira = ["yesil", "sari", "kirmizi"]
    b = df["karanlik"].notna()
    print(f"Test oyunu: {len(df)} (genel etiketi belli: {b.sum()})\n")
    for ad, sutun in (("KURAL rengi (kartın rengi)", "renk"), ("MODEL rengi (ikinci görüş)", "model_renk")):
        print(ad + ":")
        print(df.groupby(sutun).agg(oyun=("puan", "size"), karanlik=("karanlik", "mean"),
                                    gercek_agirlikli=("gercek_agirlikli", "mean")).reindex(sira)
              .to_string(float_format="%.2f"), "\n")
    y = df.loc[b, "karanlik"].astype(int)
    print(f"AUC (karanlık oyun): model {roc_auc_score(y, df.loc[b, 'genel_olas']):.3f} | "
          f"kural puanı {roc_auc_score(y, df.loc[b, 'puan']):.3f}")
    g = df["gercek_agirlikli"].notna()
    print(f"Sıra ilişkisi (ağırlıklı gerçek risk): model {spearmanr(df.loc[g, 'genel_olas'], df.loc[g, 'gercek_agirlikli'])[0]:.2f} | "
          f"kural puanı {spearmanr(df.loc[g, 'puan'], df.loc[g, 'gercek_agirlikli'])[0]:.2f}\n")
    print(f"{'Tuzak tespiti':<28}{'oyun':>5}{'tespit':>7}{'isabet':>8}{'taban':>7}{'yakalama':>9}")
    for t in sorted(kural.AGIRLIK, key=lambda t: -kural.AGIRLIK[t]):
        e = df[f"t{t}"].dropna().astype(int)
        d = df.loc[e.index, f"d{t}"].astype(bool)
        if d.sum() == 0:
            print(f"{HEDEF_TUZAKLAR[t]:<28}{len(e):>5}{0:>7}      -{e.mean():>7.2f}        -")
            continue
        print(f"{HEDEF_TUZAKLAR[t]:<28}{len(e):>5}{int(d.sum()):>7}{e[d].mean():>8.2f}{e.mean():>7.2f}{d[e == 1].mean():>9.2f}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("asama", choices=["topla", "degerlendir"])
    p.add_argument("--adet", type=int, default=None)
    a = p.parse_args()
    topla(a.adet) if a.asama == "topla" else degerlendir()
