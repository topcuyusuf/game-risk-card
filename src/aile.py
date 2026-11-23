"""Yeşilay için aileye dönük ekler (5. iyileştirme adımı). Kartın rengini DEĞİŞTİRMEZ; yalnızca bilgi ekler.

1) Çocuk bilgisi: Google Play yaş derecesi + mağaza açıklamasında açıkça çocuklara seslenen ifade
   ("perfect for kids", "for toddlers", "ages 4+"). Olumsuz cümleler ("not suitable for kids") sayılmaz.
2) Ebeveyn ipuçları: kartta bulunan her tuzak için kısa, uygulanabilir bir öneri.
3) Yeşil alternatifler: kartı YEŞİL olan (model de kırmızı demeyen), yaş derecesi daha sıkı olmayan, Play puanı
   >= 4.0 oyunlar; mağaza açıklamasına en BENZER olanlar önce (TF-IDF kosinüs benzerliği, aynı Play türüne küçük
   bonus). Benzerlik eşiği: aynı türde >= 0.04, farklı türde >= 0.12; eşiği geçen yoksa alternatif gösterilmez
   (yalnız türe göre seçim Clash of Clans'a korku oyunu öneriyordu). Orijinal oyun korku değilse korku oyunları elenir.
Kullanım (kontrol):  python src/aile.py
"""

import json
import math
import re
import sys
from collections import Counter

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

from ortak import HEDEF_TUZAKLAR, VERI

ALTERNATIF_DOSYA = VERI / "alternatifler.json"

YAS_SIRASI = {"Everyone": 0, "PEGI 3": 0, "Everyone 10+": 1, "PEGI 7": 1, "Teen": 2, "PEGI 12": 2,
              "PEGI 16": 3, "Mature 17+": 3, "PEGI 18": 4, "Adults only 18+": 4}
HER_YAS = {"Everyone", "PEGI 3"}
YAS_TR = {"Everyone": "Herkes", "Everyone 10+": "10 yaş ve üzeri", "Teen": "Genç (13+)",
          "Mature 17+": "Yetişkin (17+)", "PEGI 3": "3+", "PEGI 7": "7+", "PEGI 12": "12+", "PEGI 16": "16+",
          "PEGI 18": "18+", "Adults only 18+": "18+"}

COCUK = re.compile(
    r"\b(?:perfect|great|made|designed|ideal|fun|safe) for (?:kids|children|toddlers|preschoolers|little ones)\b"
    r"|\bfor (?:kids|children|toddlers|preschoolers|boys and girls|little ones)\b"
    r"|\bkids'? (?:game|games|app)\b|\b(?:kids|children) (?:aged|ages|of all ages)\b|\btoddlers?\b"
    r"|\bpreschool(?:ers)?\b|\bkindergarten\b|\bages? [2-9](?:\+| ?- ?\d+| and up)"
    r"|\b(?:educational|learning) games? for\b", re.I)
COCUK_OLUMSUZ = re.compile(r"(?:not|in|un)(?:appropriate|suitable)|\bnot (?:meant|intended|made|designed|for)\b"
                           r"|\bnot\b.{0,15}$", re.I)

# Tuzak başına ebeveyn ipucu (kısa, uygulanabilir; kart Türkçe olduğu için Türkçe)
IPUCU = {
    10: "Oyun belirli saatlerde girmeyi istiyor. Bildirimleri kapatın; oyun saatini oyun değil siz belirleyin.",
    11: "Günlük ödüller her gün açma alışkanlığı kurar. Bir günü kaçırmanın sorun olmadığını konuşun, bildirimleri kapatın.",
    12: "Tekrar eden görevler süreyi uzatır. Oturum başına süre sınırı koyun (Google Family Link / iPhone Ekran Süresi).",
    13: "Reklamlar oyunu böler ve başka uygulamalara yönlendirebilir. Varsa reklamsız sürümü tercih edin; "
        "oyun internetsiz çalışıyorsa uçak modunda oynatın.",
    14: "Oyunun bir sonu yok. 'Bitince bırakırız' yerine baştan bir süre belirleyin.",
    28: "Maç ortasında bırakılamıyor. Süre dolmadan önce 'son maç' uyarısı verin; yeni maça süre kalmadıysa başlamayın.",
    30: "Bekleme süreleri 'birazdan tekrar gir' döngüsü yaratır. 'Enerji doldu' bildirimlerini kapatın.",
    53: "Süreli etkinlikler acele ettirir. Bir etkinliği kaçırmanın sorun olmadığını konuşun.",
    21: "Takım/lonca sorumluluğu bırakmayı zorlaştırır. Lonca etkinliklerinin saatlerini birlikte gözden geçirin.",
    54: "Sıralama ve rekabet 'bir maç daha' isteği doğurur. Süre yerine maç sayısıyla sınır koymak daha kolay olabilir.",
    49: "Sandık / şans ödülleri talihe dayalıdır ve harcamaya yönlendirebilir. Uygulama içi satın almayı şifreyle "
        "kilitleyin, harcama sınırı koyun.",
    24: "Harcanan zaman ve para bırakmayı zorlaştırır. Ara vermenin emeği silmeyeceğini konuşun.",
    45: "Rozet ve ilerleme çubukları 'tamamlama' isteği uyandırır. Hedefi oyun değil siz koyun.",
    46: "Koleksiyonu tamamlama isteği süreyi uzatır. Tamamlamanın şart olmadığını konuşun.",
}
AD_ID = {v: k for k, v in HEDEF_TUZAKLAR.items()}

KORKU = re.compile(r"\b(?:horror|scary|creepy|terrifying|jump ?scares?|haunted|gore|gory|nightmares?)\b", re.I)
ESIK_AYNI, ESIK_FARKLI, TUR_BONUS = 0.04, 0.12, 0.05
VEKTOR_UZUNLUK = None        # kısaltma benzerliği düşürüyordu (80 terimde kapsam 259 -> 219); tam vektör saklanır


def _kelimeler(metin):
    return [w for w in re.findall(r"[a-z]{3,}", str(metin).lower()) if w not in ENGLISH_STOP_WORDS]


def idf_hesapla(aciklamalar):
    """Tüm açıklamalardan IDF. Çok yaygın (> %15) ve tek oyunda geçen kelimeler atılır ('game', 'play', 'free' …)."""
    df = Counter()
    for a in aciklamalar:
        df.update(set(_kelimeler(a)))
    n = len(aciklamalar)
    return {w: math.log(n / d) + 1 for w, d in df.items() if 2 <= d <= 0.15 * n}


def vektor(metin, idf, uzunluk=None):
    """Birim uzunlukta TF-IDF vektörü {kelime: ağırlık}."""
    v = {w: (1 + math.log(c)) * idf[w] for w, c in Counter(_kelimeler(metin)).items() if w in idf}
    z = math.sqrt(sum(x * x for x in v.values())) or 1.0
    v = {w: x / z for w, x in v.items()}
    if uzunluk:
        v = dict(sorted(v.items(), key=lambda kv: -kv[1])[:uzunluk])
    return v


def korku_mu(aciklama, kategoriler=()):
    """Açıklamada korku kelimesi ya da Play etiketi 'Horror' / 'Survival horror'."""
    return bool(KORKU.search(aciklama or "")) or any("horror" in str(k).lower() for k in kategoriler or ())


def benzerlik(a, b):
    return sum(x * b.get(w, 0.0) for w, x in a.items())


def cocuk_bilgisi(yas, aciklama):
    """{'yas': ..., 'yas_tr': ..., 'her_yas': bool, 'hedef': bool, 'alinti': str|None}"""
    alinti = None
    if yas is None or YAS_SIRASI.get(yas, 9) <= 1:          # 17+/Teen oyunda "for kids" ifadesi sayılmaz
        for m in COCUK.finditer(aciklama or ""):
            if not COCUK_OLUMSUZ.search(aciklama[max(0, m.start() - 25):m.start()]):
                alinti = " ".join(aciklama[max(0, m.start() - 40):m.end() + 30].split())
                break
    return {"yas": yas, "yas_tr": YAS_TR.get(yas, yas), "her_yas": yas in HER_YAS,
            "hedef": alinti is not None, "alinti": alinti}


def ipuclari(kart):
    """Kartta bulunan (tespit, uyarı, mağaza kanıtı) her tuzak için bir ipucu; tekrarsız, ağırlık sırasında."""
    ids = [d["tuzak_id"] for d in kart["tespitler"]] + [AD_ID[u["tuzak"]] for u in kart["uyarilar"]] \
        + [m["tuzak_id"] for m in kart.get("magaza_kanit", [])]
    return [{"tuzak": HEDEF_TUZAKLAR[t], "ipucu": IPUCU[t]} for t in dict.fromkeys(ids)]


def alternatif_tablosu(kartlar, play_bilgi, aciklamalar, kategoriler=None):
    """Yeşil kartlı oyunlar + IDF. kartlar: kart listesi; play_bilgi: oyun_id -> kayıt; aciklamalar: oyun_id -> metin;
    kategoriler: oyun_id -> Play etiketleri (korku filtresi için).
    Dönüş: {'idf': {...}, 'oyunlar': [...]}."""
    idf = idf_hesapla(list(aciklamalar.values()))
    tablo = []
    for k in kartlar:
        p = play_bilgi.get(k["oyun_id"])
        if not p or k["renk"] != "yesil" or k["model_renk"] == "kirmizi" or not p.get("genreId"):
            continue
        tablo.append({"oyun_id": k["oyun_id"], "ad": p.get("title") or k["ad"], "play_id": p["play_id"],
                      "tur": p["genreId"], "tur_ad": p.get("genre"), "yas": p.get("contentRating"),
                      "puan": p.get("score") or 0, "indirme": p.get("installs") or "",
                      "ucretsiz": bool(p.get("free")),
                      "korku": korku_mu(aciklamalar.get(k["oyun_id"], ""), (kategoriler or {}).get(k["oyun_id"])),
                      "vektor": {w: round(x, 4) for w, x in
                                 vektor(aciklamalar.get(k["oyun_id"], ""), idf, VEKTOR_UZUNLUK).items()}})
    return {"idf": {w: round(x, 4) for w, x in idf.items()}, "oyunlar": tablo}


def _indirme(s):
    return int(re.sub(r"\D", "", str(s)) or 0)


def alternatifler(tablo, tur, yas, haric=None, aciklama="", kategoriler=(), adet=3):
    """Açıklaması en benzer, yaş derecesi daha sıkı olmayan yeşil oyunlar (en çok `adet`; eşiği geçen yoksa boş)."""
    if not tablo or not tablo.get("oyunlar") or not aciklama:
        return []
    q = vektor(aciklama, tablo["idf"])
    korku = korku_mu(aciklama, kategoriler)
    sinir = YAS_SIRASI.get(yas, 0)          # yaş derecesi bilinmiyorsa en sıkısı (Herkes) varsayılır
    aday = []
    for a in tablo["oyunlar"]:
        if a["play_id"] == haric or YAS_SIRASI.get(a["yas"], 9) > sinir or a["puan"] < 4.0 or (a["korku"] and not korku):
            continue
        b, ayni = benzerlik(q, a["vektor"]), a["tur"] == tur
        if b >= (ESIK_AYNI if ayni else ESIK_FARKLI):
            aday.append((b + TUR_BONUS * ayni, _indirme(a["indirme"]), b, a))
    aday.sort(key=lambda x: (-x[0], -x[1]))
    return [{"ad": a["ad"], "play_id": a["play_id"], "puan": round(a["puan"], 1), "ucretsiz": a["ucretsiz"],
             "yas_tr": YAS_TR.get(a["yas"], a["yas"]), "benzerlik": round(b, 2)} for _, _, b, a in aday[:adet]]


def ekle(kart, magaza, aciklama, tablo):
    """Kart sözlüğüne aile alanlarını ekler (yerinde)."""
    m = magaza or {}
    kart["cocuk"] = cocuk_bilgisi(m.get("play_yas"), aciklama)
    kart["ipuclari"] = ipuclari(kart)
    kart["alternatifler"] = (alternatifler(tablo, m.get("play_tur"), m.get("play_yas"), m.get("play_id"), aciklama,
                                           m.get("play_kategoriler"))
                             if kart["renk"] != "yesil" else [])
    return kart


def alternatif_oku():
    return json.load(open(ALTERNATIF_DOSYA, encoding="utf-8")) if ALTERNATIF_DOSYA.exists() else {}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    for yas, a in [("Everyone", "Animal Jam is the best online community for kids and a safe place"),
                   ("Everyone", "It is COSMIC HORROR and is not suitable for kids."),
                   ("Teen", "a safe and entertaining show for kids and grown-ups alike"),
                   ("Everyone", "Simple controls—great for kids, too"),
                   ("Everyone", "Help Josef save Berta, kidnapped by the Black Cap Brothers")]:
        print(f"{yas:<10} {cocuk_bilgisi(yas, a)['hedef']!s:<6} {a[:60]}")
