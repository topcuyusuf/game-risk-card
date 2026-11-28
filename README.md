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
   - store signals (`src/21_magaza_sinyalleri.py`): App Store "Loot Boxes" advisory, Play
     "Competitive multiplayer" category, paid "Remove ads" products; if Google Play says the game
     has no ads, ad detections are dropped (only 5 of 186 such games had an ad trap by vote);
   - the general model as a "second opinion" and for an extra screen-time warning; if the rule
     score is yellow but the model says red, the card is raised to red (those games were 88% dark
     in development, 86% in the test) and the card says why.
3. Card colour = transparent weighted score (`src/18_kural_karti.py`): Variable Rewards 3;
   Advertisements, Wait To Play, Grinding 2; others 1. 0–1 green, 2–4 yellow, ≥ 5 red.
4. The frozen system (`src/sistem.py`) is shared by the unvoted-game cards, the independent test
   and the live demo.

## Results
| | Development (485 Play games, 5-fold CV) | Independent test (347 iOS-only games, frozen system) |
|---|---|---|
| Rule score AUC (dark game) | 0.861 | 0.855 |
| General model AUC | 0.927 | 0.895 |
| Dark share: green / yellow / red cards | 6% / 25% / 83% | 6% / 21% / 75% |

- External check against researcher-coded loot box labels (Zendle et al. 2019, Xiao et al. 2021,
  OSF), 113 matched games: 90% of the card's Variable Rewards detections had loot boxes
  (`src/26_lootbox_dogrulama.py`).
- **Real playtime check** (Open Play, Ballou et al. 2026; Steam logs of ~1,900 adults): 44 games
  with a darkpattern.games card plus 37 Steam games not on the site at all, whose official Google
  Play versions were carded by the frozen system (strict full-title matching, checked by hand).
  Compared with the same player's other games, players spend ×0.85 the time on green-card games,
  ×1.20 on yellow and ×1.78 on red – about 2× more on red than green (95% interval 1.4–3.1;
  `src/35_gercek_sure.py`, `36_open_play_play`, `37_genis_sure_testi`, `38_beklenen_sure`).
- **Colour stability** (`src/45_kararlilik.py`): two disjoint 200-review samples of the same game give
  the same colour for about 9 in 10 games. Each card is re-scored on 15 bootstrap resamples of its reviews;
  if fewer than 90% agree, it shows a "colour is borderline" note. On 473 games with 400 reviews (5-fold),
  marked cards (26%) kept their colour on a disjoint sample in 75% of cases, unmarked ones in 97%.
- Extra Wait To Play / Grinding phrases ("bonus lives", "stuck on the same level") were tried and not used
  (`src/46_kural_genisletme.py`): card-score AUC 0.861 → 0.861 (dev), 0.855 → 0.854 (test).
- **Bug fix** (`src/47_reklam_urunu.py`): a broken word-boundary pattern missed ad-removal products such as
  "Ad Removal" and "No-Ads Offer". Restoring the pattern chosen in step 22 gave 12 more games this evidence
  (7 development, 5 test). No development colour changed; two test games moved from green to yellow, so the test
  AUC went from 0.856 to 0.855. All numbers in this README use the corrected version.
- **Live demo input** (`src/48_canli_magaza_farki.py`): the live demo reads Google Play only, not App Store signals. Without
  them, on the 485 development cards the rule-score AUC is 0.833 instead of 0.861 and 34 cards (7%) get a milder colour
  (dark share: green 9%, yellow 32%, red 84%). The test results above describe the full system.
- A per-game "expected screen time" number was tried and not used: its typical error (×1.76) was
  about the same as the colour's (×1.77), so the card keeps a colour-level time sentence.
- **Turkish reviews** (`39`–`42`): a model trained on ~200 Turkish Play reviews per game reaches
  AUC 0.866 (English 0.919 on the same 408 games). Adding Turkish did not improve the card – the
  two-language model average was lower (0.906), and Turkish keyword rules changed only 3 of 51
  independent-test games – so the card stays English-based.

## For families (Yeşilay)
Each card also has a "For families" box (`src/aile.py`); it never changes the colour:
- Google Play age rating, and a "child-targeted" note when the store description explicitly
  addresses children ("perfect for kids", "for toddlers", "ages 4+"; negated phrases ignored).
- A short, practical tip for every detected trap (e.g. ads: prefer the ad-free version or play
  offline in airplane mode; loot boxes: lock in-app purchases and set a spending limit).
- For yellow/red games: up to three green-card games whose store description is most similar
  (TF-IDF cosine; same Play genre ≥ 0.04 with a small bonus, other genres ≥ 0.12), with an age rating
  no stricter than the original and a Play rating ≥ 4.0. Horror games (description words or the Play
  "Horror" tag) are only suggested for horror games. If nothing is similar enough, the card page shows
  no alternative (259 of 367 yellow/red cards get one). Genre-only matching had suggested a horror game for
  Clash of Clans; now it suggests Kingdom Rush Frontiers and Bloons TD.
- In the live demo, red cards always show three green suggestions. If too few games are similar, the list is
  completed with labelled "general suggestions" (green card, age rating no stricter than the game and at most
  Teen, Play rating ≥ 4.0, no horror, same genre first); these may not resemble the original game. On the 233 red
  development cards, 362 of the 699 suggestions are general. The list of green games stays out of this repository
  because it is derived from the vote data, so without it the demo shows a letter instead of the game icon.
- **Recommend me a game** (live demo): age group, favourite genres, liked games among the open cards and a
  free-only option give six green-card suggestions with the reason for each. Answers stay in the browser and
  recommendation requests are not logged. Usefulness has not been tested with users.
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
| Live demo | `24_demo`, `arayuz.html` (collectible-style card interface) |
| Later checks | `28`–`32` (sentence pilot, Can't Pause rule, review count), `34`–`38` (Open Play: problem gaming, real playtime), `39`–`42` (Turkish reviews), `45`–`48` (colour stability, rule extension, ad-product fix, live input check) |
| For families | `aile` (age rating, child note, parent tips, green alternatives) |

Code comments and console output are in Turkish.

## Running
```bash
pip install -r requirements.txt
python src/24_demo.py   # live demo at http://127.0.0.1:8765, paste a Google Play link
```
The demo needs the trained system (`data/model/sistem.joblib`), which is built from the
collected data. Collecting darkpattern.games data again requires the site owner's permission
and the 5-second delay set in `src/ortak.py`.
