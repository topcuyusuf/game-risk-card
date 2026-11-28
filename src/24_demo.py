"""Adım 24: Canlı demo — Google Play bağlantısını yapıştır, risk kartını gör.

Sadece bu bilgisayarda çalışır (127.0.0.1). Her istekte Google Play'den oyunun bilgisi ve
200 İngilizce yorumu çekilir; kart, dondurulmuş sistemle (src/sistem.py) üretilir.
darkpattern.games'e hiçbir istek atılmaz.
Kullanım:  python src/24_demo.py     ->  http://127.0.0.1:8765
"""

import csv
import importlib
import json
import os
import re
import threading
import unicodedata
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests
from google_play_scraper import Sort, app, reviews
from google_play_scraper.exceptions import NotFoundError

import aile
import sistem as sistem_mod
from ortak import VERI

veri_seti = importlib.import_module("09_veri_seti")

# Yerelde: 127.0.0.1:8765. Yayında (ör. Hugging Face Spaces): HOST=0.0.0.0 PORT=7860 ortam değişkenleri.
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", 8765))
# İnternete açık çalışırken koruma: aynı oyun tekrar çekilmez, kişi başı ve toplam istek sınırlanır.
ONBELLEK_SN = 6 * 3600           # bir oyunun kartı 6 saat saklanır
ONBELLEK_ADET = 500
DAKIKADA_ISTEK = 6               # bir adresten dakikada en çok 6 kart
AYNI_ANDA = threading.Semaphore(3)   # aynı anda en çok 3 Play çekimi
ONBELLEK, ISTEKLER = {}, {}
SISTEM = sistem_mod.sistemi_yukle()
_ikon_dosya = VERI / "model" / "yesil_ikonlar.json"      # öneri kartlarının görselleri (dosya yoksa harf gösterilir)
YESIL_IKON = json.load(open(_ikon_dosya, encoding="utf-8")) if _ikon_dosya.exists() else {}
_TABLO = SISTEM.get("alternatifler") or {}
TABLO_VEKTOR = {a["play_id"]: a["vektor"] for a in _TABLO.get("oyunlar", [])}
TARANAN_VEKTOR = {}                 # kartı üretilen oyunların açıklama vektörü (oyun bazında; kişi bilgisi yok)
ONERI_ISTEK, ONERI_DAKIKA = {}, 20  # "Bana oyun öner": adres başına dakikada en çok 20 istek
PAKET = re.compile(r"^[A-Za-z][\w]*(\.[A-Za-z_][\w]*)+$")
KAYIT = VERI / "demo_kayit.csv"          # her isteğin kaydı (izleme için); yorum metni yazılmaz
KAYIT_KILIDI = threading.Lock()
SAYAC = {"istek": 0, "hata": 0, "baslangic": datetime.now().isoformat(timespec="seconds")}


def kaydet(paket, sonuc, sure):
    """İsteği CSV'ye ekler: zaman, paket, durum, yorum sayısı, puan, renk, model olasılığı, süre."""
    hata = sonuc.get("hata")
    with KAYIT_KILIDI:
        SAYAC["istek"] += 1
        SAYAC["hata"] += bool(hata)
        yeni = not KAYIT.exists()
        with open(KAYIT, "a", encoding="utf-8", newline="") as f:
            yaz = csv.writer(f)
            if yeni:
                yaz.writerow(["zaman", "paket", "durum", "yorum_sayisi", "puan", "renk", "model_renk",
                              "genel_olas", "sure_sn", "hata"])
            yaz.writerow([datetime.now().isoformat(timespec="seconds"), paket or "", "hata" if hata else "tamam",
                          sonuc.get("yorum_sayisi", ""), sonuc.get("puan", ""), sonuc.get("renk", ""),
                          sonuc.get("model_renk", ""), sonuc.get("genel_olas", ""), round(sure, 1), hata or ""])

# Arayüz ayrı dosyada: koleksiyon kartı görünümü, kapatma/geri alma, en çok 12 açık kart.
SAYFA = Path(__file__).with_name("arayuz.html").read_text(encoding="utf-8")
GORSELLER = {f"/{ad}": Path(__file__).with_name(ad).read_bytes() for ad in ("logo.webp", "meme.webp")}
IKON = re.compile(r"^https://play-lh\.googleusercontent\.com/[\w\-./=]+$")   # yalnızca Google Play görselleri


def paket_adi(q):
    """Oyun sayfası bağlantısından ya da düz paket adından Play paket adını çıkarır."""
    q = q.strip()
    if "play.google.com" in q:
        q = parse_qs(urlparse(q).query).get("id", [""])[0]
    return q if PAKET.match(q) else None


ARAMA_IZINLI = re.compile(r"^[\w\s.:'&!+\-]{2,80}$")


def arama_metni(q):
    """Play arama bağlantısından (…/store/search?q=…) ya da düz oyun adından arama metnini çıkarır."""
    q = q.strip()
    if "play.google.com" in q:
        q = parse_qs(urlparse(q).query).get("q", [""])[0]
    q = " ".join(unicodedata.normalize("NFKC", q).split())
    return q if ARAMA_IZINLI.match(q) else None


def play_ara(metin):
    """Play'de arar, sonuçların paket adlarını sırasıyla döndürür (en çok 5).
    Not: google-play-scraper'ın search() fonksiyonu öne çıkan ilk sonucun kimliğini boş veriyor;
    bu yüzden arama sayfası doğrudan okunur. Adres sabittir; kullanıcı yalnızca arama metnini verir."""
    r = requests.get("https://play.google.com/store/search",
                     params={"q": metin, "c": "apps", "hl": "en", "gl": "us"},
                     headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    ids = re.findall(r"/store/apps/details\?id=([\w.]+)", r.text) if r.ok else []
    return list(dict.fromkeys(ids))[:5]


def anahtar(q):
    """Önbellek anahtarı: paket adı ya da arama metni."""
    paket = paket_adi(q)
    if paket:
        return paket
    metin = arama_metni(q)
    return "ara:" + metin.lower() if metin else None


def kart_hazirla(q):
    paket, arama = paket_adi(q), None
    if not paket:
        arama = arama_metni(q)
        if not arama:
            return {"hata": "Oyunun adını ya da Google Play bağlantısını girin."}
        bilgi = None
        for aday in play_ara(arama):                  # ilk OYUN sonucu seçilir
            try:
                b = app(aday, lang="en", country="us")
            except NotFoundError:
                continue
            if str(b.get("genreId", "")).startswith("GAME"):
                paket, bilgi = aday, b
                break
        if not bilgi:
            return {"hata": f"Google Play'de “{arama}” için oyun bulunamadı. Başka bir ad ya da oyunun bağlantısını deneyin."}
    else:
        try:
            bilgi = app(paket, lang="en", country="us")
        except NotFoundError:
            return {"hata": "Bu uygulama Google Play'de (ABD mağazası) bulunamadı."}
    gelen, _ = reviews(paket, lang="en", country="us", sort=Sort.MOST_RELEVANT, count=200)
    yorumlar = [{"metin": y["content"], "yildiz": y["score"], "faydali_oy": y["thumbsUpCount"]}
                for y in gelen if y.get("content")]
    if len(yorumlar) < 20:
        return {"hata": f"Yeterli İngilizce yorum yok ({len(yorumlar)}). Kart üretilemedi."}
    magaza = {"ios_var": False, "ios_etiketler": [], "urunler": [],
              "play_kategoriler": [k["name"] for k in bilgi.get("categories", []) if k.get("name")],
              "play_reklam": bilgi.get("containsAds"),
              "play_yas": bilgi.get("contentRating"), "play_tur": bilgi.get("genreId"), "play_id": paket}
    aciklama = (bilgi.get("summary") or "") + " " + veri_seti.html_temizle(bilgi.get("description"))
    k = sistem_mod.kart_uret(SISTEM, paket, bilgi.get("title") or paket, yorumlar, aciklama, magaza)
    if _TABLO.get("idf"):
        with KAYIT_KILIDI:
            if len(TARANAN_VEKTOR) >= 2000:
                TARANAN_VEKTOR.pop(next(iter(TARANAN_VEKTOR)))
            TARANAN_VEKTOR[paket] = aile.vektor(aciklama, _TABLO["idf"])
    notlar = []
    if arama:
        notlar.append(f"“{arama}” araması: ilk oyun sonucu {bilgi.get('title') or paket} seçildi.")
    if not str(bilgi.get("genreId", "")).startswith("GAME"):
        notlar.append("Uyarı: bu uygulama oyun kategorisinde değil; kart oyunlar için tasarlandı.")
    if len(yorumlar) < 100:
        notlar.append("Az yorum var; sonuç daha belirsiz.")
    k["not_"] = " ".join(notlar)
    k["oysuz"] = False
    ikon = bilgi.get("icon") or ""
    k["ikon"] = ikon if IKON.match(ikon) else None
    if k["renk"] == "kirmizi":                        # kırmızı kartta en çok 3 yeşil öneri
        k["alternatifler"] = aile.yesil_oneriler(SISTEM.get("alternatifler"), k.get("alternatifler"),
                                                 bilgi.get("genreId"), bilgi.get("contentRating"), paket)
    for a in k.get("alternatifler", []):
        u = YESIL_IKON.get(a["play_id"]) or ""
        a["ikon"] = u if IKON.match(u) else None
    return k


class Istek(BaseHTTPRequestHandler):
    def _yaz(self, kod, tur, govde):
        self.send_response(kod)
        self.send_header("Content-Type", tur if tur.startswith("image/") else tur + "; charset=utf-8")
        if tur.startswith("image/"):
            self.send_header("Cache-Control", "public, max-age=86400")
        self.send_header("Content-Length", str(len(govde)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
                         "img-src 'self' https://play-lh.googleusercontent.com")
        self.end_headers()
        if self.command != "HEAD":                      # HEAD: yalnızca başlıklar
            self.wfile.write(govde)

    def _izin_var(self, kayitlar=None, sinir=None):
        """Adres başına dakikalık istek sınırı. Vekil sunucu arkasında gerçek adres X-Forwarded-For'dadır."""
        kayitlar = ISTEKLER if kayitlar is None else kayitlar
        sinir = DAKIKADA_ISTEK if sinir is None else sinir
        adres = (self.headers.get("X-Forwarded-For") or self.client_address[0]).split(",")[0].strip()
        simdi = time.time()
        with KAYIT_KILIDI:
            son = [t for t in kayitlar.get(adres, []) if simdi - t < 60]
            izin = len(son) < sinir
            if izin:
                son.append(simdi)
            kayitlar[adres] = son
            if len(kayitlar) > 5000:                        # bellek şişmesin
                kayitlar.clear()
        return izin

    def _oneri(self, sorgu):
        """Bana oyun öner: yaş grubu, türler, yalnız ücretsiz, sevilen oyunlar (paket adları). Hiçbir şey kaydedilmez."""
        al = lambda ad: sorgu.get(ad, [""])[0][:600]
        yas = al("yas") if al("yas") in aile.YAS_GRUP else "cocuk"
        turler = [t for t in al("tur").split(",") if t in aile.TUR_GRUP][:10]
        begen = [p for p in al("begen").split(",") if PAKET.match(p)][:8]
        acik = [p for p in al("acik").split(",") if PAKET.match(p)][:12]
        vektor, eksik = {}, []
        for p in begen:
            v = TARANAN_VEKTOR.get(p) or TABLO_VEKTOR.get(p)
            if v:
                vektor[p] = v
            else:
                eksik.append(p)
        liste, havuz = aile.kisisel_oneriler(_TABLO, yas, turler, al("ucretsiz") == "1", vektor, set(acik) | set(begen))
        for o in liste:
            u = YESIL_IKON.get(o["play_id"]) or ""
            o["ikon"] = u if IKON.match(u) else None
        return {"oneriler": liste, "havuz": havuz, "eksik": eksik}

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/":
            self._yaz(200, "text/html", SAYFA.encode("utf-8"))
        elif u.path in GORSELLER:
            self._yaz(200, "image/webp", GORSELLER[u.path])
        elif u.path == "/api/kart":
            q = parse_qs(u.query).get("q", [""])[0][:300]
            basla = time.time()
            paket = anahtar(q)
            if not self._izin_var():
                sonuc = {"hata": "Çok fazla istek. Lütfen bir dakika sonra tekrar deneyin."}
            elif paket in ONBELLEK and basla - ONBELLEK[paket][0] < ONBELLEK_SN:
                sonuc = ONBELLEK[paket][1]                  # aynı oyun: Play'e tekrar gidilmez
            else:
                try:
                    with AYNI_ANDA:
                        sonuc = kart_hazirla(q)
                except Exception as hata:                   # ağ hatası vb.
                    sonuc = {"hata": str(hata)[:200]}
                if paket and not sonuc.get("hata"):
                    with KAYIT_KILIDI:
                        if len(ONBELLEK) >= ONBELLEK_ADET:
                            ONBELLEK.pop(min(ONBELLEK, key=lambda k: ONBELLEK[k][0]))
                        ONBELLEK[paket] = (basla, sonuc)
            kaydet(sonuc.get("oyun_id") or paket, sonuc, time.time() - basla)
            self._yaz(200, "application/json", json.dumps(sonuc, ensure_ascii=False).encode("utf-8"))
        elif u.path == "/api/oneri":
            sonuc = (self._oneri(parse_qs(u.query)) if self._izin_var(ONERI_ISTEK, ONERI_DAKIKA)
                     else {"hata": "Çok fazla istek. Lütfen bir dakika sonra tekrar deneyin."})
            self._yaz(200, "application/json", json.dumps(sonuc, ensure_ascii=False).encode("utf-8"))
        elif u.path == "/api/durum":                        # sağlık kontrolü + sayaçlar
            self._yaz(200, "application/json", json.dumps({"durum": "hazir", **SAYAC}).encode("utf-8"))
        else:
            self._yaz(404, "text/plain", b"yok")

    def do_HEAD(self):
        """Sağlık kontrolleri ve vekil sunucular için: sayfa ve durum adresi HEAD ile de yanıt verir."""
        if urlparse(self.path).path in ("/", "/api/durum"):
            self.do_GET()
        else:
            self._yaz(404, "text/plain", b"yok")

    def log_message(self, *a):                              # sessiz
        pass


if __name__ == "__main__":
    print(f"Demo hazır: http://{HOST}:{PORT}", flush=True)
    ThreadingHTTPServer((HOST, PORT), Istek).serve_forever()
