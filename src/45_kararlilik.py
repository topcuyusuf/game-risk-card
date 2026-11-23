"""Adım 45: "Renk sınırda" notu — kartın rengi yorum örneğine ne kadar bağlı?

Sorun (32. adım): aynı oyunun ortak yorumu olmayan iki 200'lük örneği, oyunların %13'ünde farklı renk veriyor.
Çözüm: kart üretilirken yorumlar yerine koyarak yeniden örneklenir (bootstrap, 15 kez) ve renk her seferinde
yeniden hesaplanır (sistem.kararlilik). Renk tekrarların %90'ından azında aynı çıkarsa kart "sınırda" notu alır
(eşik bu dosyanın eşik denemesiyle seçildi: 0.8 farklı renk verenlerin %43'ünü, 0.9 %71'ini yakalıyor).

Sınama (bu dosya): 400 yorumu olan geliştirme oyunları, 32. adımdaki gibi 5 katlı düzen (modeller o oyunu görmez).
  A = rastgele 200 yorum, B = kalan 200 yorum (ortak yorum yok).
  Not yalnızca A'dan hesaplanır; soru: not alan kartlarda A ile B'nin rengi gerçekten daha sık farklı mı?
Ayrıca 485 kartın (kart sayfası) notu aynı katlı modellerle kendi yorumlarından hesaplanır -> data/kararlilik.json
(16_kart.py bu dosyayı okur.)
Kullanım:  python src/45_kararlilik.py
"""

import importlib
import json
import random
import sys

import pandas as pd
from sklearn.model_selection import StratifiedKFold

import sistem as sistem_mod
from ortak import VERI

ilk_model = importlib.import_module("10_ilk_model")
risk = importlib.import_module("14_risk_skoru")
kart_mod = importlib.import_module("16_kart")
o32 = importlib.import_module("32_yorum_400_karsilastir")

CIKTI = VERI / "kararlilik.json"


def ys(metinler):
    return [{"metin": m, "yildiz": 1, "faydali_oy": 0} for m in metinler]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    tablo = pd.read_pickle(VERI / "oyun_tablosu.pkl").reset_index(drop=True)
    tablo["oyun_id"] = tablo["oyun_id"].astype(str)
    yorum400 = o32.yorumlari_oku()
    _, _, _, _, magaza = kart_mod.oku()
    karne = sistem_mod.sistemi_yukle()["karne"]
    kart_renk = {k["oyun_id"]: k["renk"] for k in map(json.loads, open(VERI / "kartlar.jsonl", encoding="utf-8"))}
    y_genel = risk.genel_karanlik(tablo)
    metin = tablo["yorumlar"].map(" ".join)
    hedef = {"genel_olas": y_genel, "reklam_olas": tablo["t13"], "durdurma_olas": tablo["t28"]}
    katlar = StratifiedKFold(5, shuffle=True, random_state=42).split(tablo, y_genel.fillna(0))
    r = random.Random(42)

    sinama, kart_not = [], {}
    for kat, (egitim, sinav) in enumerate(katlar, 1):
        modeller = {}
        for ad, y in hedef.items():
            b = y.iloc[egitim].notna().to_numpy()
            modeller[ad] = ilk_model.model_kur().fit(metin.iloc[egitim][b], y.iloc[egitim][b].astype(int))
        for i in sinav:
            oid, m, acik = tablo.at[i, "oyun_id"], magaza.get(tablo.at[i, "oyun_id"]), tablo.at[i, "aciklama"]
            # 1) Kart sayfası: kendi yorumlarıyla not (referans: kartın rengi)
            kendi = ys(tablo.at[i, "yorumlar"])
            renk0, _ = sistem_mod.renk_hesapla(modeller, karne, oid, kendi, acik, m)
            k = sistem_mod.kararlilik(modeller, karne, oid, kendi, kart_renk.get(oid, renk0), acik, m)
            kart_not[oid] = k | {"tam_renk_ayni": renk0 == kart_renk.get(oid)}
            # 2) Sınama: A'dan not, A ile B karşılaştırması
            if len(yorum400.get(oid, [])) >= 400:
                karisik = r.sample(yorum400[oid], 400)
                a, b = ys(karisik[:200]), ys(karisik[200:])
                renk_a, _ = sistem_mod.renk_hesapla(modeller, karne, oid, a, acik, m)
                renk_b, _ = sistem_mod.renk_hesapla(modeller, karne, oid, b, acik, m)
                ka = sistem_mod.kararlilik(modeller, karne, oid, a, renk_a, acik, m)
                sinama.append({"oyun_id": oid, "renk_a": renk_a, "renk_b": renk_b, "oran": ka["oran"],
                               "sinirda": ka["sinirda"], "ayni": renk_a == renk_b})
        print(f"kat {kat} bitti ({len(sinama)} sınama oyunu)", flush=True)

    d = pd.DataFrame(sinama)
    d.to_csv(VERI / "sonuclar_kararlilik.csv", index=False, encoding="utf-8")
    print(f"\nSınama: {len(d)} oyun (400 yorumlu), A ve B ortak yorumsuz 200'er yorum")
    print(f"Tüm kartlar: A ile B aynı renk %{100 * d.ayni.mean():.0f}")
    for ad, g in d.groupby("sinirda"):
        print(f"  {'sınırda notu' if ad else 'not yok     '}: {len(g):>3} kart (%{100 * len(g) / len(d):.0f}) | "
              f"A ile B aynı renk %{100 * g.ayni.mean():.0f}")
    print("Eşik denemesi (oran < eşik -> not):")
    for e in [0.6, 0.7, 0.8, 0.9]:
        n, y = d[d.oran < e], d[d.oran >= e]
        print(f"  eşik {e:.1f}: not alan %{100 * len(n) / len(d):.0f} (aynı renk %{100 * n.ayni.mean():.0f}) | "
              f"notsuz aynı renk %{100 * y.ayni.mean():.0f} | farklı rengi olanların notla yakalanan payı "
              f"%{100 * (~d.ayni & (d.oran < e)).sum() / max((~d.ayni).sum(), 1):.0f}")

    json.dump(kart_not, open(CIKTI, "w", encoding="utf-8"), ensure_ascii=False)
    kn = pd.DataFrame(kart_not).T
    print(f"\nKart sayfası: {len(kn)} kart, sınırda notu alan {int(kn.sinirda.sum())} "
          f"(%{100 * kn.sinirda.mean():.0f}); katlı modelle tam örnek rengi kartla aynı %{100 * kn.tam_renk_ayni.mean():.0f}")
    print(f"-> {CIKTI}, data/sonuclar_kararlilik.csv")


if __name__ == "__main__":
    main()
