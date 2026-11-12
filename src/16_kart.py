"""Adım 16: Renk + uyarılar + kanıtları tek bir risk kartında birleştirir.

Katmanlar:
  1) Renk           : AĞIRLIKLI KURAL PUANI (18. adım); genel model 'ikinci görüş' olarak durur
  2) Uyarılar       : reklam ve durdurulamama için özel model (>= 0.5)
  3) Tespit edilenler: SINAVI GEÇEN kelime kuralları + akran kıyası (15. adım)
Kullanım:  python src/16_kart.py
"""

import csv
import importlib
import json
import re

import pandas as pd
from sklearn.metrics import roc_auc_score

from ortak import HEDEF_TUZAKLAR, VERI

# Ağırlıklı kural (ağırlıklar, puan, renk eşikleri) 18. adımda tanımlı; aynısını kullanıyoruz.
kural = importlib.import_module("18_kural_karti")

CIKTI = VERI / "kartlar.jsonl"
UYARI_ESIK = 0.5
AKRAN_YUZDELIK = 0.90      # Akran eşiği: tuzaksız oyunların %90'ının konuşma oranı
MIN_KAT = 1.5              # 'Tespit' için akran eşiğinin en az 1.5 katı konuşulmalı
KURAL_AUC = 0.70           # Kural bu AUC'yi geçerse kartta gösterilir.
# Not: 'karanlık içi AUC' ile de girme yolu denendi; Infinite Treadmill bu yolla girdi ama
# tespitleri genel orandan iyi değildi (%54'e karşı %57). Bu yüzden sadece genel AUC kullanılıyor.
MODEL_TUZAKLARI = {28}     # Bu tuzakta kural yerine model kullanılır (kural zayıf, model iyi).

KATEGORI = {10: "Zamansal", 11: "Zamansal", 12: "Zamansal", 13: "Zamansal", 14: "Zamansal",
            28: "Zamansal", 30: "Zamansal", 53: "Sosyal", 21: "Sosyal", 54: "Sosyal",
            49: "Psikolojik", 24: "Psikolojik", 45: "Psikolojik", 46: "Psikolojik"}
RENK_ADI = {"yesil": "YEŞİL", "sari": "SARI", "kirmizi": "KIRMIZI"}
RENK_SIRASI = ["yesil", "sari", "kirmizi"]

# Ağırlık kuralı: ekran süresini doğrudan uzatan zamansal tuzaklar daha ağır sayılır.
# Karar: renk DEĞİŞMEZ (sadece model). Yeşil/sarı kartta güçlü zamansal sinyal varsa
# ayrıca 'Ekran süresi uyarısı' eklenir. Kırmızı kartlara eklenmez (zaten en üst seviye).
GUCLU_KAT = 2.0            # Zamansal tespit, tipik oyunun en az 2 katı konuşuluyorsa 'güçlü'
EK_UYARI_RENKLERI = {"yesil", "sari"}

# Mağaza sinyalleri (21-22. adım): oya ve yoruma bağlı olmayan, şirket beyanı / mağaza bilgisi.
# Sadece oyuncu oylarıyla güçlü örtüşen üç sinyal kullanılır (bkz. data/sonuclar_magaza_sinyal.csv).
REKLAM_URUNU = re.compile(r"remove ads?|no ads?|ad[- ]?free|ads?", re.I)
REKABET_KATEGORI = ("Competitive multiplayer", "Competitive")


def magaza_kanitlari(m):
    """Bir oyunun mağaza sinyallerinden kanıt satırları üretir (m yoksa boş liste)."""
    if not m:
        return []
    sonuc = []
    if any("Loot Boxes" in e for e in m.get("ios_etiketler", [])):
        sonuc.append({"tuzak_id": 49, "tuzak": HEDEF_TUZAKLAR[49],
                      "kanit": "App Store içerik beyanı: “Loot Boxes”"})
    kat = next((k for k in m.get("play_kategoriler", []) if k in REKABET_KATEGORI), None)
    if kat:
        sonuc.append({"tuzak_id": 54, "tuzak": HEDEF_TUZAKLAR[54],
                      "kanit": f"Google Play kategorisi: “{kat}”"})
    urun = next((u["ad"] for u in m.get("urunler", []) if REKLAM_URUNU.search(u["ad"])), None)
    if urun:
        sonuc.append({"tuzak_id": 13, "tuzak": HEDEF_TUZAKLAR[13],
                      "kanit": f"App Store’da satılan ürün: “{urun}”"})
    return sonuc


def zamansal_nedenler(kart):
    """Karttaki güçlü zamansal sinyalleri, tuzak başına tek satır olarak döndürür."""
    nedenler = {}
    for u in kart["uyarilar"]:
        if u["tuzak"] == HEDEF_TUZAKLAR[13]:
            nedenler.setdefault(u["tuzak"], []).append("model yüksek olasılık veriyor")
    for d in kart["tespitler"]:
        if d["kategori"] == "Zamansal" and d["kat"] >= GUCLU_KAT:
            nedenler.setdefault(d["tuzak"], []).append(f"tipik oyunun {d['kat']} katı konuşuluyor")
    return [f"{tuzak}: {'; '.join(n)}" for tuzak, n in nedenler.items()]


def oku():
    tablo = pd.read_pickle(VERI / "oyun_tablosu.pkl").set_index("oyun_id")
    skor = pd.read_csv(VERI / "risk_skorlari.csv", dtype={"oyun_id": str}).set_index("oyun_id")
    kanit = {}
    for satir in open(VERI / "kanitlar.jsonl", encoding="utf-8"):
        k = json.loads(satir)
        kanit[k["oyun_id"]] = k["tuzaklar"]
    with open(VERI / "oyun_linkleri.csv", encoding="utf-8", newline="") as f:
        ad = {s["oyun_id"]: s["ad"] for s in csv.DictReader(f)}   # Sadece kartta göstermek için
    magaza = {}
    if (VERI / "magaza_sinyal.jsonl").exists():
        for satir in open(VERI / "magaza_sinyal.jsonl", encoding="utf-8"):
            m = json.loads(satir)
            magaza[m["oyun_id"]] = m
    return tablo, skor, kanit, ad, magaza


def kural_karnesi(tablo, skor, oran):
    """Her tuzak için: kural gösterilsin mi, akran eşiği ne?"""
    karne = {}
    for t in HEDEF_TUZAKLAR:
        s = f"t{t}"
        y = tablo[s].dropna().astype(int)
        o = oran.loc[y.index, s]
        auc = roc_auc_score(y, o)
        kar = skor.loc[y.index, "genel_gercek"] == 1
        auc_kar = roc_auc_score(y[kar], o[kar]) if y[kar].nunique() == 2 else 0
        karne[t] = {
            "goster": auc >= KURAL_AUC and t not in MODEL_TUZAKLARI,
            "akran_esik": float(o[y == 0].quantile(AKRAN_YUZDELIK)),   # Tuzaksızların %90'lık değeri
            "auc": auc, "auc_karanlik": auc_kar,
        }
    return karne


def renk_cumlesi(renk, renk_olcegi):
    # Türkçe ek sayıya göre değiştiği için (%89'u, %4'ü) eksiz bir cümle kuruyoruz.
    return (f"Bu renkteki oyunlarda oyuncuların tuzakların çoğunu "
            f"doğruladığı oran: %{100 * renk_olcegi[renk]:.0f}")


def kart_kur(oyun_id, ad, s, kanit_oyun, karne, magaza=None):
    """TEK bir oyunun kartı.
    s: model puanları (renk, reklam_olas, durdurma_olas) | kanit_oyun: 15. adımın tuzak kanıtları
    karne: kural_karnesi() çıktısı (hangi kural gösterilir, akran eşikleri)."""
    kart = {
        "oyun_id": oyun_id, "ad": ad,
        "model_renk": s["renk"],        # İkinci görüş: genel modelin rengi
        "uyarilar": [], "tespitler": [],
    }
    if s["reklam_olas"] >= UYARI_ESIK:
        kart["uyarilar"].append({"tuzak": HEDEF_TUZAKLAR[13], "dil": "yüksek olasılık",
                                 "puan": round(float(s["reklam_olas"]), 2)})
    if s["durdurma_olas"] >= UYARI_ESIK:
        kart["uyarilar"].append({"tuzak": HEDEF_TUZAKLAR[28], "dil": "olası",
                                 "puan": round(float(s["durdurma_olas"]), 2)})

    for t, k in karne.items():
        v = kanit_oyun[str(t)]
        o = v["eslesen_yorum"] / max(v["toplam_yorum"], 1)
        esik = max(k["akran_esik"], 1 / 200)     # Eşik 0 ise en az 1 yorum say
        if k["goster"] and v["eslesen_yorum"] >= 3 and o >= MIN_KAT * esik:
            kart["tespitler"].append({
                "tuzak_id": t, "tuzak": HEDEF_TUZAKLAR[t], "kategori": KATEGORI[t],
                "eslesen": v["eslesen_yorum"], "toplam": v["toplam_yorum"],
                "kat": round(o / esik, 1),       # akran eşiğinin kaç katı
                "alintilar": v["alintilar"], "aciklamada": v["aciklamada"],
            })
    kart["tespitler"].sort(key=lambda d: -d["eslesen"])
    kart["magaza_kanit"] = magaza_kanitlari(magaza)

    # ANA RENK: ağırlıklı kural puanı (karar: kural rengi, model ikinci görüş)
    tespit = sorted(kural.tespit_edilenler(kart), key=lambda t: -kural.AGIRLIK[t])
    kart["puan"] = sum(kural.AGIRLIK[t] for t in tespit)
    kart["puan_en_fazla"] = sum(kural.AGIRLIK.values())
    kart["puan_dokumu"] = [{"tuzak": HEDEF_TUZAKLAR[t], "agirlik": kural.AGIRLIK[t]} for t in tespit]
    kart["renk"] = kural.kural_rengi(kart["puan"])
    # İkinci görüş notu: sadece model ile kural tam zıt düşerse (yeşil <-> kırmızı)
    zit = {kart["renk"], kart["model_renk"]} == {"yesil", "kirmizi"}
    kart["ikinci_gorus"] = (f"Yorumların genel tonuna bakan model bu oyunu "
                            f"{RENK_ADI[kart['model_renk']]} görüyor; sonuç belirsiz olabilir."
                            if zit else None)

    # Ekran süresi uyarısı: renk aynı kalır, sadece yeşil/sarıya not düşülür.
    kart["ekran_suresi_uyarisi"] = (zamansal_nedenler(kart)
                                    if kart["renk"] in EK_UYARI_RENKLERI else [])
    return kart


def main():
    tablo, skor, kanit, ad, magaza = oku()
    oran = pd.DataFrame({f"t{t}": {o: v[str(t)]["eslesen_yorum"] / max(v[str(t)]["toplam_yorum"], 1)
                                  for o, v in kanit.items()} for t in HEDEF_TUZAKLAR})
    karne = kural_karnesi(tablo, skor, oran)

    kartlar = [kart_kur(oyun_id, ad[oyun_id], skor.loc[oyun_id], kanit[oyun_id], karne, magaza.get(oyun_id))
               for oyun_id in tablo.index]

    # Renk ölçeği: her KURAL renginin geçmişte gerçekleşen 'karanlık' oranı (kartın ilk cümlesi).
    kural_renk = pd.Series({k["oyun_id"]: k["renk"] for k in kartlar})
    renk_olcegi = skor["genel_gercek"].groupby(kural_renk).mean()
    renk_olcegi.to_json(VERI / "renk_olcegi.json")            # Yeni oyunların kartı için saklanır
    with open(CIKTI, "w", encoding="utf-8") as f:
        for kart in kartlar:
            kart["renk_aciklama"] = renk_cumlesi(kart["renk"], renk_olcegi)
            f.write(json.dumps(kart, ensure_ascii=False) + "\n")

    # --- Sınama ---
    print("Kural karnesi:")
    for t, k in karne.items():
        durum = "MODEL" if t in MODEL_TUZAKLARI else ("göster" if k["goster"] else "gizle")
        print(f"  {HEDEF_TUZAKLAR[t]:<28}{durum:<7} AUC {k['auc']:.2f}  karanlık içi {k['auc_karanlik']:.2f}"
              f"  akran eşiği: 200 yorumda {k['akran_esik'] * 200:.0f}")

    kartlar = [json.loads(s) for s in open(CIKTI, encoding="utf-8")]
    print("\nTespitlerin isabeti (tespit edilen tuzakta etiket de 'var' mı?):")
    for t in HEDEF_TUZAKLAR:
        if not karne[t]["goster"]:
            continue
        tespit = [k["oyun_id"] for k in kartlar if any(d["tuzak_id"] == t for d in k["tespitler"])]
        etiket = tablo.loc[tespit, f"t{t}"].dropna()
        tum = tablo[f"t{t}"].dropna()
        print(f"  {HEDEF_TUZAKLAR[t]:<28} {len(tespit):>3} oyunda tespit | etiketi 'var' olan: "
              f"%{100 * etiket.mean():.0f}  (genel oran %{100 * tum.mean():.0f})")

    # Sınama: ekran süresi uyarısı alan yeşil/sarı kartlarda zamansal tuzak gerçekten daha mı çok?
    zamansal = [f"t{t}" for t, k in KATEGORI.items() if k == "Zamansal"]
    df = pd.DataFrame([{"oyun_id": k["oyun_id"], "renk": k["renk"],
                        "ek_uyari": bool(k["ekran_suresi_uyarisi"])} for k in kartlar]).set_index("oyun_id")
    df["karanlik"] = skor["genel_gercek"]
    df["zamansal_pay"] = tablo[zamansal].mean(axis=1)   # Bilinen zamansal etiketlerin 'var' payı
    print("\nRenk ölçeği ve ekran süresi uyarısı:")
    print(df.groupby(["renk", "ek_uyari"]).agg(oyun=("karanlik", "size"), karanlik=("karanlik", "mean"),
                                              zamansal_pay=("zamansal_pay", "mean"))
          .reindex(RENK_SIRASI, level=0).to_string(float_format="%.2f"))


if __name__ == "__main__":
    main()
