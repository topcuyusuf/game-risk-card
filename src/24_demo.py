"""Adım 24: Canlı demo — Google Play bağlantısını yapıştır, risk kartını gör.

Sadece bu bilgisayarda çalışır (127.0.0.1). Her istekte Google Play'den oyunun bilgisi ve
200 İngilizce yorumu çekilir; kart, dondurulmuş sistemle (src/sistem.py) üretilir.
darkpattern.games'e hiçbir istek atılmaz.
Kullanım:  python src/24_demo.py     ->  http://127.0.0.1:8765
"""

import importlib
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from google_play_scraper import Sort, app, reviews
from google_play_scraper.exceptions import NotFoundError

import sistem as sistem_mod

veri_seti = importlib.import_module("09_veri_seti")
sayfa_mod = importlib.import_module("17_kart_sayfasi")   # aynı görünüm için CSS + kart çizimi

PORT = 8765
SISTEM = sistem_mod.sistemi_yukle()
PAKET = re.compile(r"^[A-Za-z][\w]*(\.[A-Za-z_][\w]*)+$")

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
  <p class="alt">Bir Google Play oyun bağlantısı yapıştır; yorumlar okunur ve kart üretilir (~15 sn).</p>
  <form class="form" id="form">
    <input id="q" placeholder="https://play.google.com/store/apps/details?id=…" aria-label="Google Play bağlantısı" required>
    <button id="btn">Kartı üret</button>
  </form>
  <p class="ornek">Örnek: <a href="#" data-q="com.miniclip.eightballpool">8 Ball Pool</a> ·
     <a href="#" data-q="com.ustwo.monumentvalley2">Monument Valley 2</a> ·
     <a href="#" data-q="com.king.candycrushsaga">Candy Crush Saga</a></p>
  <p class="durum" id="durum"></p>
</header>
<p class="kural">Renk kuralı: tespit edilen her tuzak ağırlığı kadar puan ekler —
  Variable Rewards 3; Advertisements, Wait To Play, Grinding 2; diğerleri 1.
  0–1 puan yeşil, 2–4 sarı, 5 ve üstü kırmızı.</p>
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
    """Bağlantıdan ya da düz metinden Play paket adını çıkarır."""
    q = q.strip()
    if "play.google.com" in q:
        q = parse_qs(urlparse(q).query).get("id", [""])[0]
    return q if PAKET.match(q) else None


def kart_hazirla(q):
    paket = paket_adi(q)
    if not paket:
        return {"hata": "Geçerli bir Google Play bağlantısı ya da paket adı girin."}
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
              "play_kategoriler": [k["name"] for k in bilgi.get("categories", []) if k.get("name")]}
    aciklama = (bilgi.get("summary") or "") + " " + veri_seti.html_temizle(bilgi.get("description"))
    k = sistem_mod.kart_uret(SISTEM, paket, bilgi.get("title") or paket, yorumlar, aciklama, magaza)
    notlar = []
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
        self.end_headers()
        self.wfile.write(govde)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/":
            self._yaz(200, "text/html", SAYFA.encode("utf-8"))
        elif u.path == "/api/kart":
            q = parse_qs(u.query).get("q", [""])[0]
            try:
                sonuc = kart_hazirla(q)
            except Exception as hata:                       # ağ hatası vb.
                sonuc = {"hata": str(hata)[:200]}
            self._yaz(200, "application/json", json.dumps(sonuc, ensure_ascii=False).encode("utf-8"))
        else:
            self._yaz(404, "text/plain", b"yok")

    def log_message(self, *a):                              # sessiz
        pass


if __name__ == "__main__":
    print(f"Demo hazır: http://127.0.0.1:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Istek).serve_forever()
