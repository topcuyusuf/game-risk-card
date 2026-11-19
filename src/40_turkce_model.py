"""Adım 40: Kart Türkçe yorumlarla çalışır mı?

Etiketler oyun düzeyinde ve dilden bağımsız (darkpattern.games oyları). Aynı oyunların Türkçe yorumlarıyla
(39. adım) aynı TF-IDF + lojistik regresyon kurulur ve 5 katlı çapraz doğrulamayla ölçülür (14. adımla aynı katlar).
Karşılaştırma (yalnızca en az MIN_YORUM Türkçe yorumu olan oyunlarda):
  EN       : İngilizce yorumlarla eğit, İngilizce yorumlarla sına (şu anki sistem)
  TR       : Türkçe yorumlarla eğit, Türkçe yorumlarla sına
  EN+TR>TR : her oyunun İngilizce ve Türkçe belgesiyle birlikte eğit (tek model, iki dil), Türkçe ile sına
  EN>TR    : İngilizce modelle Türkçe yorumu puanla (kontrol; ortak kelimeler pvp, gacha, vip... yüzünden kısmen çalışır)
  EN+TR ort.: iki dilin model olasılıklarının ortalaması
Hedefler: genel 'karanlık oyun', Advertisements (t13), Can't Pause or Save (t28).
Kullanım:  python src/40_turkce_model.py
"""

import importlib
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import KFold

from ortak import VERI

ilk_model = importlib.import_module("10_ilk_model")
risk = importlib.import_module("14_risk_skoru")
o39 = importlib.import_module("39_turkce_yorumlar")

MIN_YORUM = 50


def turkce_metin():
    y = pd.read_json(o39.YORUMLAR, lines=True, dtype={"oyun_id": str})
    g = y.groupby("oyun_id").metin.agg(list)
    return g[g.map(len) >= MIN_YORUM].map(" ".join)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    tablo = pd.read_pickle(VERI / "oyun_tablosu.pkl").reset_index(drop=True)
    en = tablo["yorumlar"].map(" ".join)
    tr = tablo.oyun_id.map(turkce_metin())
    hedefler = {"karanlık oyun": risk.genel_karanlik(tablo), "Advertisements": tablo["t13"],
                "Can't Pause or Save": tablo["t28"]}
    print(f"Oyun: {len(tablo)} | en az {MIN_YORUM} Türkçe yorumu olan: {int(tr.notna().sum())}\n")

    tahmin = {(h, d): pd.Series(np.nan, index=tablo.index) for h in hedefler for d in ["EN", "TR", "EN+TR>TR", "EN>TR"]}
    for egitim, sinav in KFold(5, shuffle=True, random_state=ilk_model.TOHUM).split(tablo):
        eg, sn = tablo.index[egitim], tablo.index[sinav]
        sn_tr = sn[tr[sn].notna().to_numpy()]
        for h, y in hedefler.items():
            b = eg[y[eg].notna().to_numpy()]
            m_en = ilk_model.model_kur().fit(en[b], y[b].astype(int))
            tahmin[(h, "EN")][sn] = m_en.predict_proba(en[sn])[:, 1]
            tahmin[(h, "EN>TR")][sn_tr] = m_en.predict_proba(tr[sn_tr])[:, 1]
            b_tr = b[tr[b].notna().to_numpy()]
            m_tr = ilk_model.model_kur().fit(tr[b_tr], y[b_tr].astype(int))
            tahmin[(h, "TR")][sn_tr] = m_tr.predict_proba(tr[sn_tr])[:, 1]
            m_ik = ilk_model.model_kur().fit(pd.concat([en[b], tr[b_tr]]),
                                             pd.concat([y[b], y[b_tr]]).astype(int))
            tahmin[(h, "EN+TR>TR")][sn_tr] = m_ik.predict_proba(tr[sn_tr])[:, 1]

    ortak = tr.notna()
    print(f"AUC (yalnızca Türkçe yorumu olan oyunlar; 5 katlı çapraz doğrulama)")
    print(f"{'Hedef':<22}{'oyun':>6}{'EN':>7}{'TR':>7}{'EN+TR>TR':>10}{'EN>TR':>8}")
    satir = []
    for h, y in hedefler.items():
        m = ortak & y.notna()
        auc = {d: roc_auc_score(y[m].astype(int), tahmin[(h, d)][m]) for d in ["EN", "TR", "EN+TR>TR", "EN>TR"]}
        print(f"{h:<22}{int(m.sum()):>6}" + "".join(f"{auc[d]:>{w}.3f}" for d, w in
                                                  [("EN", 7), ("TR", 7), ("EN+TR>TR", 10), ("EN>TR", 8)]))
        ort = (tahmin[(h, "EN")][m] + tahmin[(h, "TR")][m]) / 2          # iki dilin ortalaması
        auc["EN+TR ort."] = roc_auc_score(y[m].astype(int), ort)
        print(f"{'':<28}iki dilin olasılık ortalaması: {auc['EN+TR ort.']:.3f}")
        satir.append({"hedef": h, "oyun": int(m.sum()), **auc})
    pd.DataFrame(satir).to_csv(VERI / "sonuclar_turkce.csv", index=False, encoding="utf-8")

    # Aynı oyunda iki dilin tahmini ne kadar uyumlu?
    h = "karanlık oyun"
    a, b = tahmin[(h, "EN")][ortak], tahmin[(h, "TR")][ortak]
    renk = lambda s: s.map(risk.renk)
    print(f"\nAynı oyun, EN ve TR model olasılığı: korelasyon {np.corrcoef(a, b)[0, 1]:.2f}; "
          f"aynı model rengi %{100 * (renk(a) == renk(b)).mean():.0f}")
    pd.DataFrame({f"{h}|{d}": v for (h, d), v in tahmin.items()}).assign(oyun_id=tablo.oyun_id)         .to_csv(VERI / "turkce" / "tahminler.csv", index=False, encoding="utf-8")
    print("-> data/sonuclar_turkce.csv, data/turkce/tahminler.csv")


if __name__ == "__main__":
    main()
