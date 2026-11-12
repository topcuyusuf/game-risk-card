# Game Risk Card

Predicts screen-time dark patterns in mobile games from player reviews and gives each game a
green / yellow / red risk card, with short review quotes as evidence for every detected pattern.
Samsung Innovation Campus (AI) capstone, in cooperation with Yeşilay. Author: Yusuf Topçu.

## Data
- **Labels:** player votes from [darkpattern.games](https://www.darkpattern.games), used with the
  site owner's written permission (non-commercial use, slow collection with ≥ 5 s between requests,
  source attribution). **Raw data is not redistributed**, so the `data/` folder is not included.
- **Features:** Google Play store info and ~200 English reviews per game (`google-play-scraper`);
  App Store reviews (Apple RSS) for the independent test; App Store "Loot Boxes" advisory,
  in-app product names and Play categories as store signals.
- **Label rule:** a pattern needs at least 2 votes; yes > no → 1, yes < no → 0; ties or fewer
  than 2 votes → unknown (never treated as 0).
- 14 screen-time patterns (temporal, social, psychological); see `src/ortak.py`.
- Not used as inputs (leakage / memorisation risk): the site's dark/healthy list and group scores,
  game and developer names.

## Method
1. TF-IDF (1–2 grams) + logistic regression on all reviews of a game (`src/10_ilk_model.py`).
2. Finding: most per-pattern models learn a general "dark game" shortcut; only Advertisements and
   Can't Pause or Save are pattern-specific. So the card uses:
   - keyword rules with negation handling per pattern (`src/15_kanitlar.py`), shown only when the
     rule reaches AUC ≥ 0.70, with review quotes as evidence;
   - store signals (`src/21_magaza_sinyalleri.py`);
   - the general model as a "second opinion" and for an extra screen-time warning.
3. Card colour = transparent weighted score (`src/18_kural_karti.py`): Variable Rewards 3;
   Advertisements, Wait To Play, Grinding 2; others 1. 0–1 green, 2–4 yellow, ≥ 5 red.
4. The frozen system (`src/sistem.py`) is shared by the unvoted-game cards, the independent test
   and the live demo.

## Results
| | Development (485 Play games, 5-fold CV) | Independent test (347 iOS-only games, frozen system) |
|---|---|---|
| Rule score AUC (dark game) | 0.867 | 0.856 |
| General model AUC | 0.927 | 0.896 |
| Dark share: green / yellow / red cards | 5% / 39% / 83% | 6% / 26% / 74% |

- External check against researcher-coded loot box labels (Zendle et al. 2019, Xiao et al. 2021,
  OSF), 113 matched games: 90% of the card's Variable Rewards detections had loot boxes
  (`src/26_lootbox_dogrulama.py`).
- Adding the 347 iOS games to training changed Play AUC by only +0.003 on average
  (`src/27_ios_ekleme_kontrolu.py`), so the system was kept as is and the test set stays clean.

## Code map (`src/`, run in order)
| Step | Files |
|---|---|
| Collect labels | `01_oyun_linkleri`, `02_oy_sayilari`, `03_ozet`, `04_sinir_bul` |
| Collect Play data | `05_play_eslestir` (test only), `06_play_kontrol`, `07_play_yorumlar` |
| Build dataset | `08_etiketler`, `09_veri_seti` |
| Models and experiments | `10_ilk_model`, `11_tum_tuzaklar`, `12_genel_vs_ozel`, `13_aciklama_ekle`, `14_risk_skoru` |
| Evidence and card | `15_kanitlar`, `16_kart`, `17_kart_sayfasi`, `18_kural_karti`, `sistem` |
| Unvoted games | `19_yeni_oyunlar` |
| Report figures | `20_rapor_grafikleri` (output in `cikti/grafikler/`) |
| Store signals | `21_magaza_sinyalleri`, `22_sinyal_karsilastir` |
| Independent test | `23_bagimsiz_test`, `25_ogrenilen_olasilik`, `26_lootbox_dogrulama`, `27_ios_ekleme_kontrolu` |
| Live demo | `24_demo` |

Code comments and console output are in Turkish.

## Running
```bash
pip install -r requirements.txt
python src/24_demo.py   # live demo at http://127.0.0.1:8765, paste a Google Play link
```
The demo needs the trained system (`data/model/sistem.joblib`), which is built from the
collected data. Collecting darkpattern.games data again requires the site owner's permission
and the 5-second delay set in `src/ortak.py`.
