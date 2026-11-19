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
from urllib.parse import parse_qs, urlparse

import requests
from google_play_scraper import Sort, app, reviews
from google_play_scraper.exceptions import NotFoundError

import sistem as sistem_mod
from ortak import VERI

veri_seti = importlib.import_module("09_veri_seti")
sayfa_mod = importlib.import_module("17_kart_sayfasi")   # aynı görünüm için CSS + kart çizimi

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

# Kart sayfasındaki stil ve çizim kodunu aynen kullan (iki yerde ayrı kod olmasın)
_s = sayfa_mod.SABLON
CSS = _s[_s.index("<style>") + 7:_s.index("</style>")]
KART_JS = _s[_s.index("function el("):_s.index("function ciz()")]

SAYFA = """<!doctype html><html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Oyun Risk Kartı – Demo</title><style>__CSS__
.form { display: flex; gap: 8px; flex-wrap: wrap; }
.form input { flex: 1 1 320px; padding: 12px; font-size: 15px; border-radius: 8px;
  border: 1px solid var(--cizgi); background: var(--kart); color: var(--metin); }
.form button { padding: 12px 20px; font-size: 15px; font-weight: 600; border-radius: 8px; cursor: pointer;
  border: 1px solid var(--metin); background: var(--metin); color: var(--zemin); }
.form button:disabled { opacity: .5; cursor: wait; }
.durum { color: var(--soluk); font-size: 14px; margin: 12px 0 0; min-height: 20px; }
.ornek { font-size: 13px; color: var(--soluk); margin: 8px 0 0; }
.ornek a { color: inherit; }
</style></head><body>
<header>
  <h1>Oyun Risk Kartı</h1>
  <p class="alt">Bir Google Play oyun bağlantısı yapıştır ya da oyunun adını yaz; yorumlar okunur ve kart üretilir (birkaç saniye).</p>
  <form class="form" id="form">
    <input id="q" placeholder="Oyun adı (ör. wild rift) ya da Google Play bağlantısı" aria-label="Oyun adı ya da Google Play bağlantısı" required>
    <button id="btn">Kartı üret</button>
  </form>
  <p class="ornek">Örnek: <a href="#" data-q="com.miniclip.eightballpool">8 Ball Pool</a> ·
     <a href="#" data-q="com.ustwo.monumentvalley2">Monument Valley 2</a> ·
     <a href="#" data-q="com.king.candycrushsaga">Candy Crush Saga</a></p>
  <p class="durum" id="durum"></p>
</header>
<p class="kural">Renk kuralı: tespit edilen her tuzak ağırlığı kadar puan ekler —
  Variable Rewards 3; Advertisements, Wait To Play, Grinding 2; diğerleri 1.
  0–1 puan yeşil, 2–4 sarı, 5 ve üstü kırmızı.
  Puan sarıya düştüğü hâlde yorumların genel tonuna bakan model oyunu kırmızı görüyorsa kart kırmızı olur.</p>
<main id="liste"></main>
<footer>Kart oyuncu yorumlarından otomatik çıkarılmıştır; kesin hüküm değildir.
  Model eğitimi: darkpattern.games oyuncu oyları (izinle, ticari olmayan kullanım).
  Yorumlar ve mağaza bilgisi: Google Play.</footer>
<script>
const RENK = { yesil: "YEŞİL", sari: "SARI", kirmizi: "KIRMIZI" };
__KART_JS__
const durum = document.getElementById("durum"), btn = document.getElementById("btn");
async function uret(q) {
  btn.disabled = true; durum.textContent = "Yorumlar okunuyor…";
  try {
    const r = await fetch("/api/kart?q=" + encodeURIComponent(q));
    const k = await r.json();
    if (k.hata) { durum.textContent = "Hata: " + k.hata; return; }
    durum.textContent = `${k.yorum_sayisi} yorum okundu.` + (k.not_ ? " " + k.not_ : "");
    document.getElementById("liste").prepend(kartCiz(k));
  } catch (e) { durum.textContent = "Bağlantı hatası: " + e; }
  finally { btn.disabled = false; }
}
document.getElementById("form").addEventListener("submit", e => { e.preventDefault(); uret(document.getElementById("q").value.trim()); });
document.querySelectorAll(".ornek a").forEach(a => a.addEventListener("click", e => {
  e.preventDefault(); document.getElementById("q").value = a.dataset.q; uret(a.dataset.q); }));
</script></body></html>""".replace("__CSS__", CSS).replace("__KART_JS__", KART_JS)


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
    notlar = []
    if arama:
        notlar.append(f"“{arama}” araması: ilk oyun sonucu {bilgi.get('title') or paket} seçildi.")
    if not str(bilgi.get("genreId", "")).startswith("GAME"):
        notlar.append("Uyarı: bu uygulama oyun kategorisinde değil; kart oyunlar için tasarlandı.")
    if len(yorumlar) < 100:
        notlar.append("Az yorum var; sonuç daha belirsiz.")
    k["not_"] = " ".join(notlar)
    k["oysuz"] = False
    return k


class Istek(BaseHTTPRequestHandler):
    def _yaz(self, kod, tur, govde):
        self.send_response(kod)
        self.send_header("Content-Type", tur + "; charset=utf-8")
        self.send_header("Content-Length", str(len(govde)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'")
        self.end_headers()
        if self.command != "HEAD":                      # HEAD: yalnızca başlıklar
            self.wfile.write(govde)

    def _izin_var(self):
        """Adres başına dakikalık istek sınırı. Vekil sunucu arkasında gerçek adres X-Forwarded-For'dadır."""
        adres = (self.headers.get("X-Forwarded-For") or self.client_address[0]).split(",")[0].strip()
        simdi = time.time()
        with KAYIT_KILIDI:
            son = [t for t in ISTEKLER.get(adres, []) if simdi - t < 60]
            izin = len(son) < DAKIKADA_ISTEK
            if izin:
                son.append(simdi)
            ISTEKLER[adres] = son
            if len(ISTEKLER) > 5000:                        # bellek şişmesin
                ISTEKLER.clear()
        return izin

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/":
            self._yaz(200, "text/html", SAYFA.encode("utf-8"))
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
