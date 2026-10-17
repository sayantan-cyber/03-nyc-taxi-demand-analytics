# Change log

## 17 Oct 2026 - v1 (initial release)

- Pipeline: 12 validation checks on the raw files, star schema, core metrics,
  Mann-Whitney + chi-square + robust OLS statistics, JFK hourly demand
  forecast (seasonal-naive baseline vs Holt-Winters vs SARIMAX).
- Documented data-quality facts measured from the files: 101 out-of-window
  rows, 173,015 negative-fare rows, 528,552 null passenger counts, 11,478
  physically impossible speeds (>65 mph), 2 exact duplicate groups.
- Tip analyses filter tips to <=100% of the fare and fares >= $2.50
  (flag drop) to keep vendor glitches out of the averages.
- Holt-Winters failed to converge and underperformed the naive baseline;
  reported as rejected, SARIMAX selected. See findings.
- NOT uploaded to GitHub yet; awaiting owner review.
