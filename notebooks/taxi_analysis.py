"""
Project 3: NYC Yellow Taxi Demand Analytics - reproducible pipeline.

Reads 6 monthly parquet files (19,493,620 trips, Jan-Jun 2023) from ./data/
(links in data/README.md), validates them, builds a star schema, engineers
features, runs statistical tests and a demand forecast, and saves charts
to ./visuals/ plus exports to ./data-exports/.

Run:  python notebooks/taxi_analysis.py
Deps: duckdb, pandas, numpy, matplotlib, statsmodels, scipy

Engine: DuckDB 1.5 (all SQL actually executes on the real files).
Every number in README.md and docs/ comes from this script or from
sql/02_core_analysis.sql, run on 17 Oct 2026.
"""
from pathlib import Path
import duckdb, pandas as pd, numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
DATA, VIS, EXP = ROOT / 'data', ROOT / 'visuals', ROOT / 'data-exports'
VIS.mkdir(exist_ok=True); EXP.mkdir(exist_ok=True)
INK, TEAL, GREY = '#251f21', '#73a89a', '#9a9496'
plt.rcParams.update({'font.size': 11, 'axes.spines.top': False, 'axes.spines.right': False})

con = duckdb.connect('/tmp/taxi_p3.duckdb')
con.execute("PRAGMA memory_limit='1.1GB'")
con.execute("PRAGMA temp_directory='/tmp/ducktmp'")
con.execute('PRAGMA threads=2')
import os; os.makedirs('/tmp/ducktmp', exist_ok=True)
FILES = str(DATA / 'yellow_tripdata_2023-*.parquet')
ZONES = str(DATA / 'taxi_zone_lookup.csv')

# 1. Validation checks (data quality + integrity)
print('== Validation ==')
files = sorted(DATA.glob('yellow_tripdata_2023-*.parquet'))
month_rows = con.execute(f"""
    SELECT strftime(tpep_pickup_datetime,'%Y-%m') m, COUNT(*) c FROM '{FILES}'
    WHERE tpep_pickup_datetime >= '2023-01-01' AND tpep_pickup_datetime < '2023-07-01'
    GROUP BY 1""").fetchall()
mr = dict(month_rows)
expected = {'2023-01': 3066726, '2023-02': 2914003, '2023-03': 3403660,
            '2023-04': 3288248, '2023-05': 3513664, '2023-06': 3307218}
ncols = len(con.execute(f"DESCRIBE SELECT * FROM '{files[0]}'").fetchall())
total = con.execute(f"SELECT COUNT(*) FROM '{FILES}'").fetchone()[0]
q = lambda sql: con.execute(sql).fetchone()[0]
checks = {
    'six monthly parquet files present': len(files) == 6,
    '19 columns in every file': ncols == 19,
    'per-month trip counts match expected (19.49M in-window)': mr == expected,
    'total rows read == 19,493,620': total == 19493620,
    'zone lookup has 265 zones': q(f"SELECT COUNT(*) FROM '{ZONES}'") == 265,
    'no null pickup timestamps': q(f"SELECT COUNT(*) FROM '{FILES}' WHERE tpep_pickup_datetime IS NULL") == 0,
    'exactly 101 out-of-window rows (documented)': q(f"SELECT COUNT(*) FROM '{FILES}' WHERE tpep_pickup_datetime < '2023-01-01' OR tpep_pickup_datetime >= '2023-07-01'") == 101,
    'pickup zone coverage vs lookup == 100%': q(f"""SELECT SUM(z."LocationID" IS NULL) FROM '{FILES}' t
        LEFT JOIN '{ZONES}' z ON z."LocationID"=t.PULocationID""") == 0,
    'no null payment_type': q(f"SELECT COUNT(*) FROM '{FILES}' WHERE payment_type IS NULL") == 0,
    'exactly 173,015 negative-fare rows (documented)': q(f"SELECT COUNT(*) FROM '{FILES}' WHERE fare_amount < 0") == 173015,
    'exactly 528,552 null passenger_count (documented)': q(f"SELECT COUNT(*) FROM '{FILES}' WHERE passenger_count IS NULL") == 528552,
    'exactly 11,478 trips faster than 65 mph (documented)': q(f"""SELECT COUNT(*) FROM '{FILES}'
        WHERE trip_distance / NULLIF(EPOCH(tpep_dropoff_datetime-tpep_pickup_datetime)/3600.0,0) > 65""") == 11478,
}
for name, ok in checks.items():
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
assert all(checks.values()), 'Validation failed. Inspect the raw files.'

# 2. Star schema (fact + dimensions), built with SQL - see sql/01_star_schema.sql
print('\n== Star schema ==')
con.execute(open(ROOT / 'sql' / '01_star_schema.sql').read().replace('__FILES__', FILES).replace('__ZONES__', ZONES))
for t in ('fact_trips', 'dim_zone', 'dim_date', 'dim_payment_type', 'dim_ratecode'):
    print(t, con.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0])

# 3. Core metrics (window functions, percentiles, pivots)
print('\n== Core metrics ==')
monthly = con.execute("""
    SELECT d.year_month, COUNT(*) trips, ROUND(SUM(f.total_amount)/1e6,1) revenue_musd,
           ROUND(AVG(f.trip_distance),2) avg_miles, ROUND(AVG(f.duration_min),1) avg_min,
           ROUND(100.0*SUM(CASE WHEN f.tip_amount>0 THEN 1 ELSE 0 END)/COUNT(*),1) pct_tipped
    FROM fact_trips f JOIN dim_date d ON d.date=f.pickup_date
    GROUP BY 1 ORDER BY 1""").fetchdf()
print(monthly.to_string(index=False))
monthly.to_csv(EXP / 'monthly_demand.csv', index=False)

hourly = con.execute("""
    SELECT f.day_of_week, f.hour_of_day, COUNT(*) trips
    FROM fact_trips f GROUP BY 1,2""").fetchdf()
piv = hourly.pivot(index='day_of_week', columns='hour_of_day', values='trips')
piv = piv.sort_index(); piv.index = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
piv.to_csv(EXP / 'weekday_hour_matrix.csv')
print('\nPeak hour overall:', piv.sum().idxmax(), '| peak day:', piv.sum(axis=1).idxmax())

top_zones = con.execute("""
    SELECT z."Zone", z."Borough", COUNT(*) pickups, ROUND(AVG(f.total_amount),2) avg_fare,
           RANK() OVER (ORDER BY COUNT(*) DESC) rnk
    FROM fact_trips f JOIN dim_zone z ON z."LocationID"=f."PULocationID"
    GROUP BY 1,2 ORDER BY pickups DESC LIMIT 15""").fetchdf()
top_zones.to_csv(EXP / 'top_pickup_zones.csv', index=False)
print('\nTop 5 pickup zones:'); print(top_zones.head(5).to_string(index=False))

flows = con.execute("""
    SELECT pz."Borough" pickup_borough, dz."Borough" dropoff_borough, COUNT(*) trips
    FROM fact_trips f JOIN dim_zone pz ON pz."LocationID"=f."PULocationID"
    JOIN dim_zone dz ON dz."LocationID"=f."DOLocationID"
    GROUP BY 1,2 ORDER BY trips DESC LIMIT 10""").fetchdf()
flows.to_csv(EXP / 'borough_flows.csv', index=False)
print('\nTop borough flows:'); print(flows.head(5).to_string(index=False))

tips = con.execute("""
    SELECT p.payment_name, COUNT(*) trips, ROUND(100.0*AVG(f.tip_pct),2) avg_tip_pct,
           ROUND(100.0*MEDIAN(f.tip_pct),2) median_tip_pct
    FROM fact_trips f JOIN dim_payment_type p ON p.payment_type=f.payment_type
    WHERE f.tip_pct IS NOT NULL AND f.tip_pct <= 1 AND f.fare_amount >= 2.50 GROUP BY 1 ORDER BY trips DESC""").fetchdf()
tips.to_csv(EXP / 'tip_by_payment.csv', index=False)
print('\nTip % by payment type:'); print(tips.to_string(index=False))

dist = con.execute("""
    SELECT CASE WHEN f.trip_distance < 1 THEN '0-1 mi' WHEN f.trip_distance < 3 THEN '1-3 mi'
                WHEN f.trip_distance < 6 THEN '3-6 mi' WHEN f.trip_distance < 12 THEN '6-12 mi'
                ELSE '12+ mi' END band,
           COUNT(*) trips, ROUND(AVG(f.fare_amount),2) avg_fare,
           ROUND(AVG(f.tip_pct)*100,2) avg_tip_pct, ROUND(AVG(f.speed_mph),1) avg_speed
    FROM fact_trips f WHERE f.speed_mph <= 65 AND f.fare_amount > 0
    GROUP BY 1 ORDER BY MIN(f.trip_distance)""").fetchdf()
dist.to_csv(EXP / 'distance_bands.csv', index=False)
print('\nDistance bands:'); print(dist.to_string(index=False))

# 4. Statistical analysis
print('\n== Statistics ==')
from scipy import stats as st
card = con.execute("""SELECT tip_pct FROM fact_trips WHERE payment_type=1 AND tip_pct IS NOT NULL
                      AND tip_pct <= 1 AND fare_amount >= 2.50 USING SAMPLE 200000""").fetchdf()['tip_pct'].to_numpy()
jfk = con.execute("""SELECT f.tip_pct FROM fact_trips f JOIN dim_zone z ON z."LocationID"=f."DOLocationID"
                     WHERE f.payment_type=1 AND z."Borough"='Queens' AND f.tip_pct IS NOT NULL AND f.tip_pct <= 1 AND f.fare_amount >= 2.50 USING SAMPLE 100000""").fetchdf()['tip_pct'].to_numpy()
man = con.execute("""SELECT f.tip_pct FROM fact_trips f JOIN dim_zone z ON z."LocationID"=f."DOLocationID"
                     WHERE f.payment_type=1 AND z."Borough"='Manhattan' AND f.tip_pct IS NOT NULL AND f.tip_pct <= 1 AND f.fare_amount >= 2.50 USING SAMPLE 100000""").fetchdf()['tip_pct'].to_numpy()
u, p_mw = st.mannwhitneyu(man, jfk, alternative='two-sided')
print(f'Mann-Whitney tip% Manhattan vs Queens (card payments): U={u:.3e}, p={p_mw:.3e}')
print(f'  medians: Manhattan {np.median(man)*100:.2f}% vs Queens {np.median(jfk)*100:.2f}%')

# chi-square: payment type x pickup borough
ct = con.execute("""
    SELECT z."Borough", f.payment_type, COUNT(*) c
    FROM fact_trips f JOIN dim_zone z ON z."LocationID"=f."PULocationID"
    WHERE f.payment_type IN (1,2) AND z."Borough" NOT IN ('Unknown','EWR')
    GROUP BY 1,2""").fetchdf().pivot(index='Borough', columns='payment_type', values='c').fillna(0)
chi2, p_chi, dof, _ = st.chi2_contingency(ct)
n = ct.to_numpy().sum()
print(f'Chi-square payment x borough: chi2={chi2:.0f}, dof={dof}, p={p_chi:.3e}, Cramers V={np.sqrt(chi2/(n*1)):.3f}')

# OLS: what moves tip % (card payments, sampled)
samp = con.execute("""
    SELECT f.tip_pct*100 tip_pct, f.trip_distance, f.duration_min, f.hour_of_day,
           f.is_rush_hour::INT is_rush_hour, f.congestion_surcharge
    FROM fact_trips f
    WHERE f.payment_type=1 AND f.tip_pct IS NOT NULL AND f.tip_pct <= 1
      AND f.fare_amount >= 2.50 AND f.trip_distance>0
    USING SAMPLE 300000""").fetchdf()
import statsmodels.api as sm
X = sm.add_constant(samp[['trip_distance','duration_min','hour_of_day','is_rush_hour']])
ols = sm.OLS(samp['tip_pct'], X).fit(cov_type='HC3')
print('\nOLS tip% ~ distance + duration + hour + rush hour (HC3 robust SE, n=300k):')
print(ols.summary2().tables[1].round(3).to_string())
print(f'R2={ols.rsquared:.4f}')
pd.DataFrame({'term': ols.params.index, 'coef': ols.params.values, 'p': ols.pvalues.values}).to_csv(EXP / 'tip_regression.csv', index=False)

# 5. Demand forecast: hourly pickups at the top zone
print('\n== Forecast ==')
top_zone_id = con.execute("""SELECT "PULocationID" FROM fact_trips GROUP BY 1 ORDER BY COUNT(*) DESC LIMIT 1""").fetchone()[0]
top_zone_name = con.execute(f"""SELECT "Zone" FROM dim_zone WHERE "LocationID"={top_zone_id}""").fetchone()[0]
ts = con.execute(f"""
    SELECT date_trunc('hour', pickup_datetime) hr, COUNT(*) trips
    FROM fact_trips WHERE "PULocationID"={top_zone_id} GROUP BY 1 ORDER BY 1""").fetchdf().set_index('hr')['trips'].asfreq('h', fill_value=0)
train, test = ts[:'2023-05'], ts['2023-06']
print(f'Forecast target: hourly pickups at {top_zone_name} (zone {top_zone_id}); train {len(train)}h, test {len(test)}h')

def mape(a, f): a, f = np.asarray(a, float), np.asarray(f, float); return 100*np.mean(np.abs((a-f)/np.maximum(a,1)))
naive = train.iloc[-168:].to_numpy(); naive_fc = np.tile(naive, 5)[:len(test)]
from statsmodels.tsa.holtwinters import ExponentialSmoothing
hw = ExponentialSmoothing(train, trend='add', damped_trend=True, seasonal='add', seasonal_periods=168).fit(optimized=True)
hw_fc = hw.forecast(len(test)).to_numpy()
print(f'MAPE seasonal-naive(168h): {mape(test, naive_fc):.1f}%  |  Holt-Winters(damped): {mape(test, hw_fc):.1f}%')
sarima_note = ''
try:
    sar = sm.tsa.SARIMAX(train, order=(1,0,1), seasonal_order=(1,0,1,24),
                         enforce_stationarity=False, enforce_invertibility=False).fit(disp=False, maxiter=100)
    sar_fc = sar.forecast(len(test)).to_numpy()
    print(f'MAPE SARIMAX(1,0,1)(1,0,1,24): {mape(test, sar_fc):.1f}%')
except Exception as e:
    sar_fc = None; sarima_note = f'SARIMAX did not converge: {e}'
    print(sarima_note)
pd.DataFrame({'hour': test.index, 'actual': test.to_numpy(), 'seasonal_naive': naive_fc,
              'holt_winters': hw_fc, **({'sarimax': sar_fc} if sar_fc is not None else {})}).to_csv(EXP / 'forecast_june.csv', index=False)

# 6. Charts
fig, ax = plt.subplots(figsize=(10, 4.2))
im = ax.imshow(piv / 1e6, aspect='auto', cmap='summer_r')
ax.set_xticks(range(24)); ax.set_yticks(range(7)); ax.set_yticklabels(piv.index)
ax.set_title('Trips by weekday and hour (millions, Jan-Jun 2023)', fontsize=13, weight='bold')
ax.set_xlabel('Hour of day')
fig.colorbar(im, ax=ax, shrink=.8)
fig.tight_layout(); fig.savefig(VIS / '01_weekday_hour_heatmap.png', dpi=150); plt.close(fig)

fig, ax = plt.subplots(figsize=(9, 4.2))
ax.bar(monthly['year_month'], monthly['trips'] / 1e6, color=TEAL)
ax.set_title('Monthly trips, yellow taxis (millions)', fontsize=13, weight='bold')
ax.set_ylabel('Trips (M)'); ax.tick_params(axis='x', rotation=30)
fig.tight_layout(); fig.savefig(VIS / '02_monthly_demand.png', dpi=150); plt.close(fig)

z = top_zones.head(10).iloc[::-1]
fig, ax = plt.subplots(figsize=(9, 4.8))
ax.barh(z['Zone'], z['pickups'] / 1e6, color=[TEAL if i == len(z) - 1 else GREY for i in range(len(z))])
ax.set_title('Top 10 pickup zones (millions of trips)', fontsize=13, weight='bold'); ax.set_xlabel('Trips (M)')
fig.tight_layout(); fig.savefig(VIS / '03_top_zones.png', dpi=150); plt.close(fig)

tp = tips[tips['payment_name'].isin(['Credit card', 'Cash', 'No charge', 'Dispute'])]
fig, ax = plt.subplots(figsize=(8, 4.2))
ax.bar(tp['payment_name'], tp['avg_tip_pct'], color=[TEAL, GREY, GREY, GREY][:len(tp)])
ax.set_title('Average tip % of fare by payment type', fontsize=13, weight='bold'); ax.set_ylabel('Tip %')
fig.tight_layout(); fig.savefig(VIS / '04_tip_by_payment.png', dpi=150); plt.close(fig)

fig, ax = plt.subplots(figsize=(9, 4.2))
ax.plot(dist['band'], dist['avg_tip_pct'], marker='o', color=INK, label='avg tip %')
ax2 = ax.twinx(); ax2.bar(dist['band'], dist['trips'] / 1e6, color=GREY, alpha=.45, label='trips (M)')
ax2.set_ylabel('Trips (M)'); ax.set_ylabel('Tip %'); ax2.spines['right'].set_visible(False)
ax.set_title('Tip % and volume by trip-distance band', fontsize=13, weight='bold')
fig.tight_layout(); fig.savefig(VIS / '05_distance_bands.png', dpi=150); plt.close(fig)

fig, ax = plt.subplots(figsize=(10, 4.2))
ax.plot(test.index, test.to_numpy(), color=INK, lw=1, label='actual')
ax.plot(test.index, hw_fc, color=TEAL, lw=1, label='Holt-Winters forecast')
ax.set_title(f'June 2023 hourly demand at {top_zone_name}: actual vs forecast', fontsize=13, weight='bold')
ax.legend(); fig.autofmt_xdate()
fig.tight_layout(); fig.savefig(VIS / '06_forecast_june.png', dpi=150); plt.close(fig)

print('\nPipeline complete. Charts in visuals/, exports in data-exports/.')
