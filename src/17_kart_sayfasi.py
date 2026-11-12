"""Adım 17: Risk kartlarını tek bir HTML sayfasına dönüştürür (internetsiz çalışır).

Sayfa: arama kutusu + renk filtresi + kart listesi.
Çıktı yerel dosyadır, yayımlanmaz (ham veri yeniden yayımlanmaz şartı).
Kullanım:  python src/17_kart_sayfasi.py
"""

import json

from ortak import KOK, VERI

CIKTI = KOK / "cikti" / "risk_kartlari.html"

SABLON = r"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Oyun Risk Kartları</title>
<style>
:root {
  --zemin: #f6f5f2; --kart: #ffffff; --metin: #1d1d1b; --soluk: #6b6a66; --cizgi: #e3e1dc;
  --yesil: #2e7d4f; --yesil-zemin: #e6f2ea; --sari: #9a6b00; --sari-zemin: #fbf1d6;
  --kirmizi: #b3261e; --kirmizi-zemin: #f9e3e1; --uyari: #8a4b00; --uyari-zemin: #fff4e0;
}
@media (prefers-color-scheme: dark) {
  :root {
    --zemin: #161615; --kart: #212120; --metin: #ecebe7; --soluk: #a3a29d; --cizgi: #34332f;
    --yesil: #6fcf97; --yesil-zemin: #1d3326; --sari: #f2c14e; --sari-zemin: #3a3017;
    --kirmizi: #f28b82; --kirmizi-zemin: #3d1f1c; --uyari: #ffb74d; --uyari-zemin: #352812;
  }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--zemin); color: var(--metin);
       font: 15px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
header { max-width: 860px; margin: 0 auto; padding: 24px 16px 8px; }
h1 { font-size: 24px; margin: 0 0 4px; }
.alt { color: var(--soluk); margin: 0 0 16px; }
.arac { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
input[type=search] { flex: 1 1 240px; padding: 10px 12px; font-size: 15px; border-radius: 8px;
  border: 1px solid var(--cizgi); background: var(--kart); color: var(--metin); }
.filtre button { padding: 8px 12px; border-radius: 999px; border: 1px solid var(--cizgi);
  background: var(--kart); color: var(--metin); cursor: pointer; font-size: 14px; }
.filtre button[aria-pressed=true] { border-color: var(--metin); font-weight: 600; }
.sayac { color: var(--soluk); font-size: 14px; margin: 12px 0 0; }
main { max-width: 860px; margin: 0 auto; padding: 8px 16px 40px; }
.kart { background: var(--kart); border: 1px solid var(--cizgi); border-left: 6px solid var(--r);
        border-radius: 12px; padding: 16px; margin: 12px 0; }
.kart[data-renk=yesil] { --r: var(--yesil); --rz: var(--yesil-zemin); }
.kart[data-renk=sari] { --r: var(--sari); --rz: var(--sari-zemin); }
.kart[data-renk=kirmizi] { --r: var(--kirmizi); --rz: var(--kirmizi-zemin); }
.ust { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
.ust h2 { font-size: 18px; margin: 0; overflow-wrap: anywhere; }
.rozet { flex: none; background: var(--rz); color: var(--r); font-weight: 700; font-size: 13px;
         padding: 4px 10px; border-radius: 999px; letter-spacing: .04em; }
.puan { font-size: 14px; margin: 6px 0 0; overflow-wrap: anywhere; }
.tahmin { display: inline-block; font-size: 12px; margin: 6px 0 0; padding: 2px 8px; border-radius: 6px;
          background: var(--zemin); border: 1px solid var(--cizgi); color: var(--soluk); }
.oran { color: var(--soluk); font-size: 14px; margin: 2px 0 10px; }
.not { font-size: 13px; color: var(--soluk); border: 1px dashed var(--cizgi); border-radius: 8px;
       padding: 6px 10px; margin: 0 0 8px; }
.kural { max-width: 860px; margin: 0 auto; padding: 0 16px; font-size: 13px; color: var(--soluk); }
.kutu { background: var(--uyari-zemin); color: var(--uyari); border-radius: 8px;
        padding: 8px 12px; margin: 8px 0; font-size: 14px; }
.kutu b { display: block; margin-bottom: 2px; }
.magaza { border: 1px solid var(--cizgi); border-radius: 8px; padding: 8px 12px; margin: 8px 0; font-size: 14px; }
.magaza b { display: block; margin-bottom: 2px; }
.magaza ul { margin: 0; padding-left: 18px; }
.kutu ul { margin: 0; padding-left: 18px; }
.tespit { border-top: 1px solid var(--cizgi); padding: 10px 0 2px; }
.tespit .baslik { font-weight: 600; }
.tespit .kat { color: var(--soluk); font-weight: 400; font-size: 13px; }
blockquote { margin: 6px 0; padding: 4px 0 4px 12px; border-left: 3px solid var(--cizgi);
             color: var(--metin); font-size: 14px; overflow-wrap: anywhere; }
.yildiz { color: var(--soluk); font-size: 12px; white-space: nowrap; }
.aciklama { color: var(--soluk); font-size: 13px; margin: 2px 0 6px; overflow-wrap: anywhere; }
.bos { color: var(--soluk); font-size: 14px; margin: 6px 0 0; }
footer { max-width: 860px; margin: 0 auto; padding: 0 16px 32px; color: var(--soluk); font-size: 13px; }
.daha { display: block; margin: 16px auto; padding: 10px 16px; border-radius: 8px; cursor: pointer;
        border: 1px solid var(--cizgi); background: var(--kart); color: var(--metin); font-size: 14px; }
</style>
</head>
<body>
<header>
  <h1>Oyun Risk Kartları</h1>
  <p class="alt">Ekran süresini artıran tasarım tuzakları — __SAYI__ oyun
    (__OYSUZ__ tanesinin oyuncu oyu yok, kartı tamamen tahmin)</p>
  <div class="arac">
    <input id="ara" type="search" placeholder="Oyun ara…" aria-label="Oyun ara">
    <div class="filtre" role="group" aria-label="Renk filtresi">
      <button data-f="hepsi" aria-pressed="true">Hepsi</button>
      <button data-f="yesil" aria-pressed="false">Yeşil</button>
      <button data-f="sari" aria-pressed="false">Sarı</button>
      <button data-f="kirmizi" aria-pressed="false">Kırmızı</button>
      <button data-f="oysuz" aria-pressed="false">Oyu yok (tahmin)</button>
    </div>
  </div>
  <p class="sayac" id="sayac"></p>
</header>
<p class="kural">Renk kuralı: tespit edilen her tuzak ağırlığı kadar puan ekler —
  Variable Rewards 3; Advertisements, Wait To Play, Grinding 2; diğerleri 1.
  0–1 puan yeşil, 2–4 sarı, 5 ve üstü kırmızı.</p>
<main id="liste"></main>
<footer>
  Kartlar oyuncu yorumlarından otomatik çıkarılmıştır; kesin hüküm değildir.
  Etiket kaynağı: darkpattern.games (izinle, ticari olmayan kullanım).
  Yorumlar ve açıklamalar: Google Play. Samsung Innovation Campus + Yeşilay projesi.
</footer>
<script id="veri" type="application/json">__VERI__</script>
<script>
// Not: Yorum metinleri her zaman textContent ile yazılır, HTML olarak yorumlanmaz.
const KARTLAR = JSON.parse(document.getElementById("veri").textContent);
const RENK = { yesil: "YEŞİL", sari: "SARI", kirmizi: "KIRMIZI" };
const SAYFA = 30;
let filtre = "hepsi", arama = "", gosterilen = SAYFA;

function el(etiket, sinif, metin) {
  const e = document.createElement(etiket);
  if (sinif) e.className = sinif;
  if (metin !== undefined) e.textContent = metin;
  return e;
}
function sayi(x) { return String(x).replace(".", ","); }
// Arama için sadeleştirme: Türkçe ı/İ ile İngilizce i/I aynı sayılır ("UNISON" = "Unison").
function sade(s) {
  return s.toLowerCase().replace(/ı/g, "i").replace(/i̇/g, "i");
}

function kartCiz(k) {
  const kart = el("article", "kart"); kart.dataset.renk = k.renk;
  const ust = el("div", "ust");
  ust.append(el("h2", "", k.ad), el("span", "rozet", RENK[k.renk]));
  kart.append(ust);
  if (k.oysuz) kart.append(el("p", "tahmin", "Bu oyunun darkpattern.games'te hiç oyu yok — kart tamamen yorumlardan tahmin edildi."));
  const puan = el("p", "puan");
  puan.append(el("b", "", `Ağırlıklı tuzak puanı: ${k.puan}/${k.puan_en_fazla}`));
  if (k.puan_dokumu.length) {
    puan.append(document.createTextNode(" — " + k.puan_dokumu.map(p => `${p.tuzak} (${p.agirlik})`).join(" + ")));
  }
  kart.append(puan, el("p", "oran", k.renk_aciklama));
  if (k.ikinci_gorus) kart.append(el("p", "not", "ⓘ " + k.ikinci_gorus));

  if (k.magaza_kanit.length) {
    const kutu = el("div", "magaza"); kutu.append(el("b", "", "🏷 Mağaza kanıtı"));
    const ul = el("ul");
    k.magaza_kanit.forEach(m => ul.append(el("li", "", `${m.tuzak}: ${m.kanit}`)));
    kutu.append(ul); kart.append(kutu);
  }
  if (k.uyarilar.length) {
    const kutu = el("div", "kutu"); kutu.append(el("b", "", "⚠ Uyarılar"));
    const ul = el("ul");
    k.uyarilar.forEach(u => ul.append(el("li", "", `${u.tuzak}: ${u.dil}`)));
    kutu.append(ul); kart.append(kutu);
  }
  if (k.ekran_suresi_uyarisi.length) {
    const kutu = el("div", "kutu"); kutu.append(el("b", "", "⏱ Ekran süresi uyarısı"));
    const ul = el("ul");
    k.ekran_suresi_uyarisi.forEach(n => ul.append(el("li", "", n.replace(/(\d)\.(\d)/g, "$1,$2"))));
    kutu.append(ul); kart.append(kutu);
  }
  if (!k.tespitler.length && !k.magaza_kanit.length) {
    kart.append(el("p", "bos", "Yorumlarda belirgin bir tuzak kanıtı bulunmadı."));
  }
  k.tespitler.forEach(d => {
    const t = el("div", "tespit");
    const b = el("div", "baslik", `${d.tuzak} `);
    b.append(el("span", "kat", `· ${d.kategori} · ${d.eslesen}/${d.toplam} yorum · tipik oyunun ${sayi(d.kat)} katı`));
    t.append(b);
    d.alintilar.forEach(a => {
      const q = el("blockquote", "", `“${a.metin}” `);
      q.append(el("span", "yildiz", "★".repeat(a.yildiz) + "☆".repeat(5 - a.yildiz)));
      t.append(q);
    });
    if (d.aciklamada) t.append(el("p", "aciklama", `Oyun açıklamasında: “${d.aciklamada}”`));
    kart.append(t);
  });
  return kart;
}

function ciz() {
  const liste = document.getElementById("liste"); liste.replaceChildren();
  const a = sade(arama);
  const uyan = KARTLAR.filter(k => (filtre === "hepsi" || k.renk === filtre ||
                                    (filtre === "oysuz" && k.oysuz)) &&
                                   sade(k.ad).includes(a));
  uyan.slice(0, gosterilen).forEach(k => liste.append(kartCiz(k)));
  document.getElementById("sayac").textContent = `${uyan.length} kart`;
  if (uyan.length > gosterilen) {
    const d = el("button", "daha", `Daha fazla göster (${uyan.length - gosterilen} kaldı)`);
    d.onclick = () => { gosterilen += SAYFA; ciz(); };
    liste.append(d);
  }
}

document.getElementById("ara").addEventListener("input", e => { arama = e.target.value; gosterilen = SAYFA; ciz(); });
document.querySelectorAll(".filtre button").forEach(b => b.addEventListener("click", () => {
  filtre = b.dataset.f; gosterilen = SAYFA;
  document.querySelectorAll(".filtre button").forEach(x => x.setAttribute("aria-pressed", x === b));
  ciz();
}));
ciz();
</script>
</body>
</html>
"""


def main():
    kartlar = [json.loads(s) for s in open(VERI / "kartlar.jsonl", encoding="utf-8")]
    yeni_dosya = VERI / "yeni" / "kartlar.jsonl"          # 19. adım: oyu olmayan oyunlar
    if yeni_dosya.exists():
        kartlar += [json.loads(s) for s in open(yeni_dosya, encoding="utf-8")]
    sira = {"kirmizi": 0, "sari": 1, "yesil": 2}
    kartlar.sort(key=lambda k: (not k.get("oysuz", False), sira[k["renk"]], -k["puan"], k["ad"].lower()))

    # Sayfada sadece gerekli alanlar: oyun_id ve iç puanlar dışarıda kalır.
    sade = [{
        "ad": k["ad"], "renk": k["renk"], "renk_aciklama": k["renk_aciklama"],
        "puan": k["puan"], "puan_en_fazla": k["puan_en_fazla"], "puan_dokumu": k["puan_dokumu"],
        "ikinci_gorus": k["ikinci_gorus"], "oysuz": k.get("oysuz", False),
        "magaza_kanit": [{"tuzak": m["tuzak"], "kanit": m["kanit"]} for m in k.get("magaza_kanit", [])],
        "uyarilar": [{"tuzak": u["tuzak"], "dil": u["dil"]} for u in k["uyarilar"]],
        "ekran_suresi_uyarisi": k["ekran_suresi_uyarisi"],
        "tespitler": [{"tuzak": d["tuzak"], "kategori": d["kategori"], "eslesen": d["eslesen"],
                       "toplam": d["toplam"], "kat": d["kat"], "aciklamada": d["aciklamada"],
                       "alintilar": [{"metin": a["metin"], "yildiz": a["yildiz"]} for a in d["alintilar"]]}
                      for d in k["tespitler"]],
    } for k in kartlar]

    # '</' dizisi veri içinde script etiketini erken kapatmasın diye kaçırılır.
    veri = json.dumps(sade, ensure_ascii=False).replace("</", "<\\/")
    html = (SABLON.replace("__VERI__", veri).replace("__SAYI__", str(len(sade)))
            .replace("__OYSUZ__", str(sum(k["oysuz"] for k in sade))))
    CIKTI.parent.mkdir(exist_ok=True)
    CIKTI.write_text(html, encoding="utf-8")
    print(f"{len(sade)} kart -> {CIKTI}  ({CIKTI.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
