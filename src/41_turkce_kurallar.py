"""Adım 41: Türkçe anahtar kelime kuralları (kanıt alıntıları için).

Kartın şeffaf kısmı İngilizce kelime kurallarıdır (15. adım). Türkçe yorumlarda aynı işi yapacak bir sözlük
yazıldı. Türkçede olumsuzluk çoğunlukla SONRA gelir ("reklam yok", "reklamsız"), bu yüzden olumsuzluk
kontrolü eşleşmenin hem önüne hem arkasına bakar. "kasıyor" (donma) gibi yanıltıcı kelimeler kullanılmaz.
Ölçüm (yalnızca Türkçe yorumu olan aynı oyunlarda, İngilizce kurallarla yan yana):
  1) Her tuzak: oyunda kurala uyan yorum payı -> o tuzağın oyuncu etiketi (AUC)
  2) Kart puanı: tespit edilen tuzakların ağırlıklı toplamı -> karanlık oyun (AUC); EN, TR ve 'EN veya TR'.
     Hangi kuralın gösterileceği (AUC >= 0.70) ve akran eşiği 5 katlı çapraz doğrulamayla eğitim katında belirlenir.
Kullanım:  python src/41_turkce_kurallar.py
"""

import importlib
import re
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import KFold

from ortak import HEDEF_TUZAKLAR, VERI

kanitlar = importlib.import_module("15_kanitlar")
kart_mod = importlib.import_module("16_kart")
kural = importlib.import_module("18_kural_karti")
risk = importlib.import_module("14_risk_skoru")
ilk_model = importlib.import_module("10_ilk_model")
o40 = importlib.import_module("40_turkce_model")

SOZLUK_TR = {
    10: r"her \d+ saatte|belirli saatlerde|alarm kur|saatinde gir|gece kalk",
    11: r"günlük (?:ödül|giriş|görev|bonus|hediye|sandık)|her gün gir|giriş ödül|seriyi? (?:boz|kaybet)",
    12: r"\bgrind|\bfarm(?:la|lamak|lıyor|layarak)|tekrar tekrar|aynı (?:bölüm|seviye|şey)\w* (?:tekrar|sürekli)"
        r"|\bsıkıcı|\bmonoton",
    13: r"rekl[aâ]m",
    14: r"sonu yok|sonu gelmiyor|bitmek bilmeyen|bitmeyen|\bsonsuz|\bamaçsız",
    28: r"duraklat|kaydedemiyor|kayıt (?:yok|alm)|ilerleme\w* (?:silin|gitti|kayboldu|sıfırlan)"
        r"|bağlantı\w* (?:kop|hata|sorun)|oyundan at(?:ıl|ıyor|tı)|\bafk\b",
    30: r"beklemek zorunda|(?:saat|dakika|gün) bekle|bekleme süre|enerji\w* bit|can(?:ım|ın|lar\w*) bit"
        r"|can(?:ların)? dolma|enerji\w* dol|\benerji",
    53: r"sınırlı süre|süreli (?:etkinlik|teklif|paket)|kaçırdı|kaçırma|etkinlik\w* (?:bit|sona)|\bfomo\b",
    21: r"\blonca|\bklan|\bittifak|klandan at|loncadan at",
    54: r"\bpvp\b|sıralama|\blig\b|rekabet|\brakip|eşleştirme|eşleşme|\barena\b|dereceli",
    49: r"\bgacha|sandık|kasa(?:lar|dan|yı|ları)? aç|kasalar|şans oran|düşme oran|\bçark|kutu aç|ganimet",
    24: r"(?:yıl|ay)(?:dır|lardır|larca) oyn|para harca|emek ver|hesab\w* (?:silin|banlan|gitti|çalın)"
        r"|tüm ilerleme|bütün ilerleme|her şeyim gitti",
    45: r"başarım|\brozet|savaş bileti|battle ?pass|ilerleme çubu",
    46: r"koleksiyon|hepsini topla|bütün karakter|tüm karakter|\balbüm",
}
KURALLAR_TR = {t: re.compile(k, re.I) for t, k in SOZLUK_TR.items()}
# Olumsuzluk: önde ("hiç reklam", "çok az reklam") ya da arkada ("reklam yok", "reklamsız", "reklam olmaması")
ONCE_TR = re.compile(r"\b(?:hiç|az|çok az|neredeyse hiç|sıfır)\W+(?:\w+\W+)?$", re.I)
SONRA_TR = re.compile(r"^\w*(?:sız|siz|suz|süz)\b|^\w*\W+(?:\w+\W+){0,2}?(?:yok|yoktu|değil|olmaması|olmadığı"
                      r"|olmuyor|bulunmuyor|görmedim|çıkmıyor|almadım)\b", re.I)


def normal(metin):
    """Türkçe küçük harf: 'İ'.lower() -> 'i̇' (noktalı) sorununu düzeltir."""
    return str(metin).replace("İ", "i").replace("I", "ı").lower()


def olumlu_tr(kural_re, metin):
    """Kurala uyan, önünde ya da arkasında olumsuzluk olmayan ilk eşleşme."""
    for m in kural_re.finditer(metin):
        once, sonra = metin[max(0, m.start() - 30):m.start()], metin[m.end():m.end() + 40]
        if not ONCE_TR.search(once) and not SONRA_TR.search(sonra):
            return m
    return None


def paylar(yorum_listeleri, kurallar, eslestir):
    """oyun x tuzak: kurala olumlu uyan yorum payı ve sayısı."""
    pay, sayi = {}, {}
    for oyun, yorumlar in yorum_listeleri.items():
        for t, k in kurallar.items():
            n = sum(eslestir(k, y) is not None for y in yorumlar)
            pay.setdefault(f"t{t}", {})[oyun], sayi.setdefault(f"t{t}", {})[oyun] = n / max(len(yorumlar), 1), n
    return pd.DataFrame(pay), pd.DataFrame(sayi)


def tespitler(tablo, pay, sayi):
    """5 katlı CV: eğitim katında göster/akran eşiği; sınav katında tespit (oyun x tuzak, 0/1)."""
    tespit_df = pd.DataFrame(0, index=tablo.index, columns=[t for t in kural.AGIRLIK if t not in kart_mod.MODEL_TUZAKLARI])
    for eg, sn in KFold(5, shuffle=True, random_state=ilk_model.TOHUM).split(tablo):
        eg, sn = tablo.index[eg], tablo.index[sn]
        for t, a in kural.AGIRLIK.items():
            if t in kart_mod.MODEL_TUZAKLARI:
                continue
            s = f"t{t}"
            y = tablo.loc[eg, s].dropna().astype(int)
            if y.nunique() < 2 or roc_auc_score(y, pay.loc[y.index, s]) < kart_mod.KURAL_AUC:
                continue
            esik = max(pay.loc[y.index[y == 0], s].quantile(kart_mod.AKRAN_YUZDELIK), 1 / 200)
            tespit_df.loc[sn, t] = ((sayi.loc[sn, s] >= 3) & (pay.loc[sn, s] >= kart_mod.MIN_KAT * esik)).astype(int)
    return tespit_df


def puanla(tespit_df):
    return sum(kural.AGIRLIK[t] * tespit_df[t] for t in tespit_df.columns)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    tablo = pd.read_pickle(VERI / "oyun_tablosu.pkl").reset_index(drop=True)
    tr_y = pd.read_json(o40.o39.YORUMLAR, lines=True, dtype={"oyun_id": str})
    tr_g = tr_y.groupby("oyun_id").metin.agg(list)
    tr_g = tr_g[tr_g.map(len) >= o40.MIN_YORUM]
    tablo = tablo[tablo.oyun_id.isin(tr_g.index)].reset_index(drop=True)
    print(f"Türkçe yorumu olan oyun: {len(tablo)}\n")

    en = {i: list(y) for i, y in tablo.yorumlar.items()}
    tr = {i: [normal(m) for m in tr_g[o]] for i, o in tablo.oyun_id.items()}
    pay_en, sayi_en = paylar(en, kanitlar.KURALLAR, kanitlar.olumlu_eslesme)
    pay_tr, sayi_tr = paylar(tr, KURALLAR_TR, olumlu_tr)

    print(f"{'Tuzak':<28}{'oyun':>5}{'EN AUC':>8}{'TR AUC':>8}   TR örnek eşleşme payı (var / yok)")
    for t in HEDEF_TUZAKLAR:
        s = f"t{t}"
        y = tablo[s].dropna().astype(int)
        if y.nunique() < 2:
            continue
        a_en, a_tr = roc_auc_score(y, pay_en.loc[y.index, s]), roc_auc_score(y, pay_tr.loc[y.index, s])
        p1, p0 = pay_tr.loc[y.index[y == 1], s].mean(), pay_tr.loc[y.index[y == 0], s].mean()
        print(f"{HEDEF_TUZAKLAR[t][:27]:<28}{len(y):>5}{a_en:>8.3f}{a_tr:>8.3f}   %{100 * p1:.1f} / %{100 * p0:.1f}")

    karanlik = risk.genel_karanlik(tablo)
    b = karanlik.notna()
    te_en, te_tr = tespitler(tablo, pay_en, sayi_en), tespitler(tablo, pay_tr, sayi_tr)
    for ad, te in {"EN": te_en, "TR": te_tr, "EN veya TR": te_en | te_tr}.items():
        pu = puanla(te)
        print(f"\nKart puanı ({ad} kuralları) -> karanlık oyun AUC: {roc_auc_score(karanlik[b], pu[b]):.3f}", end="")
        print(" | karanlık payı yeşil/sarı/kırmızı: " + " / ".join(
            f"%{100 * karanlik[b & (pu.map(kural.kural_rengi) == r)].mean():.0f}" for r in ["yesil", "sari", "kirmizi"]))
    print("\nÖrnek Türkçe kanıtlar:")
    for t in [13, 30, 49, 21]:
        for i in tablo.index:
            m = next((y for y in tr[i] if olumlu_tr(KURALLAR_TR[t], y)), None)
            if m and tablo.loc[i, f"t{t}"] == 1:
                mm = olumlu_tr(KURALLAR_TR[t], m)
                print(f"  {HEDEF_TUZAKLAR[t]}: …{m[max(0, mm.start() - 60): mm.end() + 60]}…")
                break


if __name__ == "__main__":
    main()
