"""Adım 15: Her oyun ve tuzak için şeffaf kelime kurallarıyla kanıt alıntıları çıkarır.

Her tuzağın bir kelime listesi var (aşağıda, herkes okuyabilir).
- Olumsuz cümle ("no ads", "without timers") kanıt sayılmaz.
- Kanıt gücü: o oyunun yorumlarından kaçı kurala uyuyor.
- Alıntı: kurala uyan, en çok 'faydalı' oyu almış yorumdan ilgili cümle.
Kullanım:  python src/15_kanitlar.py
"""

import json
import re
from collections import defaultdict

import pandas as pd
from sklearn.metrics import roc_auc_score

from ortak import HEDEF_TUZAKLAR, VERI

CIKTI = VERI / "kanitlar.jsonl"
MIN_YORUM = 3          # Kart "kanıt bulundu" demek için en az kaç yorum eşleşmeli
ALINTI_SAYISI = 2
ALINTI_UZUNLUK = 220

# Tuzak kelime sözlüğü (İngilizce yorumlar için). \b = kelime sınırı.
SOZLUK = {
    10: r"come back (?:at|every|in)\b|every \d+ ?hours?|set (?:an|my) alarm"
        r"|at (?:a |certain |specific )?(?:times?|hours?) of the day|check in every|wake up at",
    11: r"daily (?:rewards?|login|log-in|bonus|quests?|missions?|tasks?)|login (?:rewards?|bonus)"
        r"|log ?in every ?day|\bstreaks?\b|\bdailies\b",
    12: r"\bgrind(?:ing|y|s)?\b|\brepetitive\b|\btedious\b|\bfarming\b|same (?:levels?|stages?) over",
    13: r"\bads?\b|\badverts?\b|advertisements?|\bcommercials?\b|watch (?:a |an )?(?:video|ad)",
    14: r"never[- ]ending|\bendless\b|no end\b|\bno ending\b|goes on forever|never ends"
        r"|no way to (?:finish|win|beat)|\bpointless\b",
    28: r"can'?t pause|cannot pause|no pause|can'?t save|cannot save|no save"
        r"|lose (?:all )?(?:my |your )?progress|\bafk\b|penalt(?:y|ies) for (?:leaving|quitting)"
        r"|can'?t (?:leave|quit)|\bdisconnect(?:s|ed|ion)?\b",
    30: r"\bwait(?:ing)? (?:for|hours|\d+)|\btimers?\b|\benergy\b|\bstamina\b|out of lives"
        r"|lives (?:refill|run out)|\bcool ?downs?\b|come back later",
    53: r"limited[- ]time|time[- ]limited|miss(?:ed)? out|\bexclusive\b|only available"
        r"|\bfomo\b|\bexpire[sd]?\b|event (?:ends?|is over)",
    21: r"\bguilds?\b|\bclans?\b|\balliances?\b|let (?:my|your|the) (?:team|guild|clan) down"
        r"|kicked (?:from|out)",
    54: r"\bpvp\b|\bleaderboards?\b|\branked\b|\branking\b|\barena\b|\bcompet(?:e|itive|ition)\b"
        r"|\bmatchmaking\b|\bopponents?\b",
    49: r"\bgacha\b|loot ?box(?:es)?|drop rates?|\bpulls?\b|\bsummon(?:s|ing)?\b|\brng\b"
        r"|random rewards?|\bchests?\b",
    24: r"spent (?:so much|years|months|hundreds|thousands|\$)|years of progress|\binvested\b"
        r"|lose everything|all my progress|account (?:banned|reset|deleted|wiped)",
    45: r"\bachievements?\b|\bbadges?\b|\btroph(?:y|ies)\b|battle ?pass|progress bar|\bmilestones?\b",
    46: r"collect (?:them all|all)|catch (?:them|'em) all|complete (?:the|my) (?:set|collection)"
        r"|\bcollections?\b|\balbum\b|every character|all the characters",
}
KURALLAR = {t: re.compile(k, re.I) for t, k in SOZLUK.items()}

# Eşleşmeden önce (en fazla 5 kelime arayla) gelen olumsuzluk / azlık ifadeleri.
# "very few ads", "minimal ads" de sorun kanıtı değildir.
# Örnek: "there isn't a bunch of challenges or limited time offers" -> sayılmaz.
OLUMSUZ = re.compile(r"\b(?:no|not|without|never|zero|isn'?t|aren'?t|don'?t|doesn'?t"
                     r"|nothing like|free of|few|minimal|hardly any|barely any|rarely)\b"
                     r"(?:\W+\w+){0,5}\W*$", re.I)
# Kelime geçse de tuzak anlamına gelmeyen deyimler
DEYIMLER = re.compile(r"can'?t wait|cannot wait|couldn'?t wait", re.I)


def olumlu_eslesme(kural, metin):
    """Metinde kurala uyan, önünde olumsuzluk olmayan ve deyim olmayan ilk eşleşmeyi döndürür."""
    for m in kural.finditer(metin):
        once = metin[max(0, m.start() - 60):m.start()]
        cevre = metin[max(0, m.start() - 10):m.end() + 5]
        if not OLUMSUZ.search(once) and not DEYIMLER.search(cevre):
            return m
    return None


def cumleyi_kes(metin, m):
    """Eşleşmenin geçtiği cümleyi (gerekirse kısaltarak) döndürür."""
    bas = max(metin.rfind(i, 0, m.start()) for i in ".!?\n") + 1
    son_adaylar = [metin.find(i, m.end()) for i in ".!?\n"]
    son = min([s for s in son_adaylar if s != -1], default=len(metin)) + 1
    cumle = " ".join(metin[bas:son].split())
    if len(cumle) > ALINTI_UZUNLUK:                  # Çok uzunsa eşleşmenin çevresini al
        merkez = m.start() - bas
        bas2 = max(0, merkez - ALINTI_UZUNLUK // 2)
        cumle = "…" + cumle[bas2:bas2 + ALINTI_UZUNLUK].strip() + "…"
    return cumle


def yorumlari_sirala(yorumlar):
    """Önce şikâyetler (1-3 yıldız), sonra faydalı oya göre: alıntı önce sorun anlatandan seçilir."""
    return sorted(yorumlar, key=lambda y: (y["yildiz"] > 3, -(y["faydali_oy"] or 0)))


def oyun_kanitlari(yorumlar, aciklama):
    """TEK bir oyun için 14 tuzağın kanıtları. yorumlar: yorumlari_sirala() ile sıralı liste."""
    sonuc = {}
    for t, kural in KURALLAR.items():
        eslesen = []
        for y in yorumlar:
            m = olumlu_eslesme(kural, y["metin"])
            if m:
                eslesen.append((y, m))
        acik_m = olumlu_eslesme(kural, aciklama or "")
        sonuc[str(t)] = {
            "eslesen_yorum": len(eslesen),
            "toplam_yorum": len(yorumlar),
            "kanit_var": len(eslesen) >= MIN_YORUM,
            "alintilar": [{"metin": cumleyi_kes(y["metin"], m), "yildiz": y["yildiz"],
                           "faydali_oy": y["faydali_oy"]}
                          for y, m in eslesen[:ALINTI_SAYISI]],
            "aciklamada": cumleyi_kes(aciklama, acik_m) if acik_m else None,
        }
    return sonuc


def main():
    tablo = pd.read_pickle(VERI / "oyun_tablosu.pkl")
    oyunlar = set(tablo["oyun_id"])
    aciklama = dict(zip(tablo["oyun_id"], tablo["aciklama"]))

    # Yorumları oyun bazında sırala: önce şikâyetler (1-3 yıldız), sonra faydalı oya göre.
    # Böylece alıntı olarak önce "sorun anlatan" yorumlar seçilir.
    yorumlar = defaultdict(list)
    for satir in open(VERI / "play_yorumlar.jsonl", encoding="utf-8"):
        y = json.loads(satir)
        if y["oyun_id"] in oyunlar and y["metin"]:
            yorumlar[y["oyun_id"]].append(y)
    yorumlar = {o: yorumlari_sirala(liste) for o, liste in yorumlar.items()}

    oran = pd.DataFrame(0.0, index=sorted(oyunlar), columns=[f"t{t}" for t in HEDEF_TUZAKLAR])
    with open(CIKTI, "w", encoding="utf-8") as f:
        for oyun_id in sorted(oyunlar):
            tuzaklar = oyun_kanitlari(yorumlar[oyun_id], aciklama[oyun_id])
            for t, v in tuzaklar.items():
                oran.loc[oyun_id, f"t{t}"] = v["eslesen_yorum"] / max(v["toplam_yorum"], 1)
            f.write(json.dumps({"oyun_id": oyun_id, "tuzaklar": tuzaklar}, ensure_ascii=False) + "\n")

    # --- Kuralları sına ---
    t_index = tablo.set_index("oyun_id")
    skor = pd.read_csv(VERI / "risk_skorlari.csv", dtype={"oyun_id": str}).set_index("oyun_id")
    print(f"{len(oyunlar)} oyun için kanıt çıkarıldı -> {CIKTI.name}\n")
    print(f"{'Tuzak':<28}{'kanıt: var':>11}{'kanıt: yok':>11}{'AUC':>6}{'karanlık içi AUC':>18}")
    for t, ad in HEDEF_TUZAKLAR.items():
        s = f"t{t}"
        bilinen = t_index[s].notna()
        y = t_index.loc[bilinen, s].astype(int)
        o = oran.loc[y.index, s]
        kanit = o * 200 >= MIN_YORUM                     # yaklaşık: 200 yorumda en az 3
        auc = roc_auc_score(y, o)
        # Zor test: sadece genel olarak karanlık oyunlar arasında
        kar = skor.loc[y.index, "genel_gercek"] == 1
        auc_kar = roc_auc_score(y[kar], o[kar]) if y[kar].nunique() == 2 else float("nan")
        print(f"{ad:<28}{100 * kanit[y == 1].mean():>10.0f}%{100 * kanit[y == 0].mean():>10.0f}%"
              f"{auc:>6.2f}{auc_kar:>12.2f} (n={kar.sum()}, var={y[kar].sum()})")


if __name__ == "__main__":
    main()
