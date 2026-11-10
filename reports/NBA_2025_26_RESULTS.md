# NBA 2025–2026: frozen chronological experiment

Training: 2023–2024; residual calibration: 2024–2025; holdout: 2025–2026. The 2022–2023 season supplies initial league history. Cup championship games excluded; quarterfinals/semifinals that count as regular season retained. Each team must already have ten completed current-season regular games, before the target Athens day. No target-day results are used.

1075 eligible games; 979 with matched actual ESPN named-provider closing prices. 96 without historical prices omitted, with no replacement odds/lines. Price capture timestamps unavailable: this is a retrospective closing-price simulation, not evidence those prices were executable at an earlier application calculation time.

| Model | Bets | Won/lost | Hit rate | Units | ROI | Home Brier |
|---|---:|---:|---:|---:|---:|---:|
| original | 245 | 127/118 | 51.84% | -3.53 | -1.44% | 0.2178 |
| candidate | 99 | 47/52 | 47.47% | -11.09 | -11.20% | 0.2032 |
| pace | 252 | 132/120 | 52.38% | -0.84 | -0.33% | 0.2178 |

All models use identical quote coverage and fixed 70% / odds >=1.50 / EV >=3% policy, at most one choice per match per model. Different models select different fixtures. Win rate counts the selected tips; Brier evaluates all eligible home-win forecasts. Original means RECOMMEND1 classic model with separate uncertainty; pace means the existing possessions experiment with verified complete boxes. 1230 actual 2025–2026 boxscores were available.

The new candidate improves home-win Brier but worsens the betting result. It did NOT pass the fixed release gate (>=50 tips, >=70% hit rate, positive profit and better home Brier). No parameters or thresholds were retuned on this test. It is retained only for experimental comparisons. Existing saved history remains unchanged. No NBA model is presented as historically verified for the target.

Reproduce (public downloads, no user DB):

```sh
python nba_research/fetch.py
OPENBLAS_NUM_THREADS=1 python nba_research/train.py
python nba_research/odds.py
python nba_research/pace.py
python backtest_nba.py data/nba_research
python check_nba_model.py data/nba_research
```

The fitting script writes profile_frozen_before_test.json before test scoring; keep that file/hash. Data and cached responses belong under ignored data/nba_research/. Source receipts and response hashes are preserved in quote snapshots. Performance is not a guarantee for future seasons.
