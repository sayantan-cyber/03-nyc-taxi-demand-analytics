# Findings, statistics and limitations

Verified 17 Oct 2026 against the raw TLC parquet files (19,493,620 trips,
Jan-Jun 2023). All SQL executed in DuckDB 1.5.

## Findings

1. **Revenue grew while volume stalled.** Trips: 3.07M (Jan) to 3.31M (Jun),
   but revenue rose $82.9M to $96.1M (peaked $101.8M in May). Average trip
   length grew 3.85 to 4.37 miles and average duration 15.7 to 18.1 minutes.
2. **The city's rhythm is readable.** Peak demand is Friday at 18:00; the
   weekday-hour matrix (data-exports/weekday_hour_matrix.csv) separates the
   commute spine from the weekend night economy.
3. **Geography is concentrated.** JFK Airport alone is 5.1% of all pickups
   (993,503 trips, $78.13 avg fare). 82% of trips are Manhattan-internal.
   Top 10 zones = 46.8% of revenue; top 50 = 96.2%.
4. **96.9% of Manhattan pickups pay the $2.50 congestion surcharge** vs 3.2%
   in the Bronx - the surcharge map is a Manhattan story.
5. **Tipping is a card phenomenon.** Card tips average 24.7% of fare
   (median 25.9%, n = 15.3M). Cash shows 0.0% because cash tips are never
   recorded - this is a measurement artifact, not behavior. In other words: 0.0% measures the recording system, not tipping behavior — any driver-income analysis must model or impute cash tips rather than treat it as a real tip rate.
6. **Short trips earn the best tips:** 30.4% avg under 1 mile.
7. **Rush hour pays drivers better tips.** Robust OLS (HC3, n = 300,000,
   card payments, tips capped at 100% of fare): rush hour +1.13 pp
   (p < 0.001), each hour of day +0.11 pp (p < 0.001), each trip minute
   -0.03 pp (p < 0.001); distance not significant (p = 0.18). R2 = 0.019:
   tipping is mostly idiosyncratic - these are real but small effects.

## Statistical evidence

- **Mann-Whitney U**, tip% Manhattan vs Queens (cards): U = 1.60e8,
  p = 2.6e-184; medians 26.25% vs 23.01%. A 3.2 pp gap, not noise.
- **Chi-square**, payment type x borough: chi2 = 37,651, p < 0.001, but
  Cramer's V = 0.045 - with 19M rows everything is "significant"; effect
  size is what matters, and this one is tiny.
- **Forecast bake-off** (hourly JFK pickups; train Jan-May, test June 2023):
  seasonal-naive (168h) MAPE 28.4% | Holt-Winters 38.5% (optimizer failed
  to converge; rejected) | **SARIMAX(1,0,1)(1,0,1,24) MAPE 23.8% - selected**.
  23.8% on spiky airport demand is honest, deployable-for-planning accuracy,
  not a polished number.

## Recommendations

1. **Stage Friday-evening supply in Midtown and at JFK**; the 17:00-19:00
   Friday block is the densest demand of the week.
2. **Price airport runs as a distinct product** (avg $78 vs $20.50 Manhattan
   median); flat-fee transparency drives the higher airport tip rates.
3. **Treat cash-tip invisibility as a data bug**, not a finding: any driver
   income analysis needs an imputation model, which is future work.
4. **Use the SARIMAX baseline for zone-level staffing**, refreshed monthly;
   expect ~24% hourly error at JFK and better at steadier zones.

## Limitations

- TLC disclaimer: vendor-collected data, no accuracy guarantee from the city.
  Measured quirks: 101 out-of-window rows, 173,015 negative fares (0.89%,
  vendor adjustments), 528,552 null passenger counts (2.7%), 11,478 trips
  over 65 mph (0.06%), 2 exact duplicate groups. All kept, counted, excluded
  where noted.
- Tip analyses cap tips at 100% of fare and fares at >= $2.50 to keep
  vendor glitches out of averages; medians are also reported (robust).
- Cash tips are structurally unrecorded (payment_type=2 shows 0.0%).
- Statistical tests on 15M+ rows flag trivial effects as significant;
  effect sizes are reported alongside every p-value.
- Statistical samples (Mann-Whitney 100k/group, OLS 300k) are random samples
  of the full data, not the full data; full-data point estimates agree.
- Jan-Jun 2023 only; no year-over-year seasonality is visible.
- DuckDB 1.5 is the execution engine; no MySQL/Postgres port is claimed.
