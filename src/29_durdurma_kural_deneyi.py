"""Adım 29: Can't Pause or Save kuralını cümle pilotuna göre düzeltme denemesi (OLUMSUZ SONUÇ).

Pilot (28. adım): eski kurala uyan cümlelerin sadece %13'ü tuzaktan bahsediyor (çoğu 'disconnect', 'afk').
Yeni kural: ceza / duraklatamama ifadeleri. Cümlede daha temiz (8 yakalama, 5 doğru), AMA oyun düzeyinde
AUC 0.478: oyuncuların 'Can't Pause' oyu aslında 'gerçek zamanlı çevrim içi oyun' (MOBA, nişancı, strateji)
demek; yorumlar bunu 'can't pause' diye yazmıyor. Model (AUC 0.897) bunu zaten öğreniyor; Play kategorisi
(Multiplayer/Offline) eklemek de geliştirmedi. Karar: kart değişmedi, Can't Pause için model kalıyor.
Kullanım:  python src/29_durdurma_kural_deneyi.py   (sonuçları ekrana yazar)
"""
import importlib, json, re, sys
import os; os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
from sklearn.metrics import roc_auc_score
sys.stdout.reconfigure(encoding="utf-8")
kn = importlib.import_module("15_kanitlar")

YENI = re.compile(
    r"can'?t pause|cannot pause|unable to pause|no (?:way to |option to |ability to )?pause"
    r"|can'?t save|cannot save|no (?:way to |option to |ability to )?save (?:the game|your game|mid|during)"
    r"|(?:penalt(?:y|ies|ized)|punish\w*|\bban(?:s|ned)?\b|suspen\w*) (?:\w+ ){0,4}(?:for |when |if )?(?:you |i )?(?:leav\w*|quit\w*|disconnect\w*|afk|clos\w* the app|exit\w*)"
    r"|intentional(?:ly)? (?:disconnect|left|leav|quit)"
    r"|(?:leav|quit|exit)\w* (?:a |the |an? )?(?:match|game|battle|raid|event)\w* (?:\w+ ){0,4}(?:penalt|\bban|lose|lost|loss)"
    r"|lose (?:my |your |all |the )?(?:trophies|rank|points|stars|streak|progress|run) (?:\w+ ){0,3}(?:if|when|because|after) (?:you |i |it )?(?:leave|quit|disconnect|close|exit|pause)"
    r"|can'?t (?:join|play|queue|enter) (?:\w+ ){0,4}for (?:\d+|one|an?|half) (?:min|hour)"
    r"|(?:moves?|put|goes?|go) (?:the app |the game )?(?:in)?to (?:the )?background|minimi[sz]\w* the (?:app|game)",
    re.I)

# 1) Pilot cümleleri
p = pd.read_csv("data/cumle/havuz_t28.csv")
p["eski"] = p.cumle.map(lambda c: bool(kn.olumlu_eslesme(kn.KURALLAR[28], c)))
p["yeni"] = p.cumle.map(lambda c: bool(kn.olumlu_eslesme(YENI, c)))
for k in ("eski", "yeni"):
    x = p[k]
    print(f"Pilot {k}: yakalanan {x.sum()} | doğru {p.etiket[x].sum()} | 8 olumludan bulunan {x[p.etiket == 1].sum()}")
print(p[p.yeni & (p.etiket == 0)].cumle.str[:120].to_string())

# 2) Geliştirme oyunları (485): oyun başına eşleşen yorum sayısı
tablo = pd.read_pickle("data/oyun_tablosu.pkl").set_index("oyun_id")
kart = {json.loads(s)["oyun_id"]: json.loads(s) for s in open("data/kartlar.jsonl", encoding="utf-8")}
skor = pd.read_csv("data/risk_skorlari.csv", dtype={"oyun_id": str}).set_index("oyun_id")
d = pd.DataFrame(index=tablo.index)
d["y"] = tablo.t28
d["eski_n"] = [sum(bool(kn.olumlu_eslesme(kn.KURALLAR[28], y)) for y in tablo.at[i, "yorumlar"]) for i in d.index]
d["yeni_n"] = [sum(bool(kn.olumlu_eslesme(YENI, y)) for y in tablo.at[i, "yorumlar"]) for i in d.index]
d["n"] = tablo.yorumlar.map(len)
d["model"] = skor.loc[d.index, "durdurma_olas"]
b = d[d.y.notna()].copy(); b["y"] = b.y.astype(int)
print(f"\nGeliştirme: {len(b)} oyun, taban {b.y.mean():.2f}")
for k in ("eski_n", "yeni_n"):
    print(f"AUC {k}: {roc_auc_score(b.y, b[k] / b.n):.3f} | en az 1 eşleşen oyun: {(b[k] >= 1).sum()}")
def ol(ad, x):
    print(f"{ad:<34} tespit {x.sum():>3} | isabet {b.y[x].mean():.2f} | yakalama {x[b.y == 1].mean():.2f}")
ol("Model >= 0.5 (şimdiki kart)", b.model >= 0.5)
for n in (1, 2, 3):
    ol(f"Yeni kural >= {n} yorum", b.yeni_n >= n)
    ol(f"Model >= 0.5 VE yeni kural >= {n}", (b.model >= 0.5) & (b.yeni_n >= n))
ol("Model >= 0.3 VE yeni kural >= 1", (b.model >= 0.3) & (b.yeni_n >= 1))
b.to_csv("data/cumle/durdurma_dev.csv")
