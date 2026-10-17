-- 02_core_analysis.sql - DuckDB 1.5, runs after 01_star_schema.sql.
-- Ten analyses: window functions, percentiles, pivots, moving averages,
-- self-joins. __FILES__/__ZONES__ are substituted by the runner script.

-- Q1. Daily demand with 7-day moving average and day-over-day change
WITH daily AS (
    SELECT pickup_date, COUNT(*) trips
    FROM fact_trips GROUP BY 1
)
SELECT pickup_date, trips,
       ROUND(AVG(trips) OVER (ORDER BY pickup_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)) AS trips_ma7,
       ROUND(100.0*(trips - LAG(trips) OVER (ORDER BY pickup_date))
             / LAG(trips) OVER (ORDER BY pickup_date), 1) AS dod_change_pct
FROM daily ORDER BY 1;

-- Q2. Fare and tip percentiles by borough (exact percentiles, not approximations)
SELECT z."Borough", COUNT(*) trips,
       ROUND(MEDIAN(f.total_amount),2) median_fare,
       ROUND(QUANTILE_CONT(f.total_amount, 0.9),2) p90_fare,
       ROUND(QUANTILE_CONT(f.total_amount, 0.99),2) p99_fare,
       ROUND(100.0*QUANTILE_CONT(f.tip_pct, 0.5),1) median_tip_pct
FROM fact_trips f JOIN dim_zone z ON z."LocationID"=f."PULocationID"
WHERE f.fare_amount >= 2.50 AND f.tip_pct <= 1 AND f.payment_type=1
GROUP BY 1 ORDER BY trips DESC;

-- Q3. Rush-hour premium: same borough pair, rush vs off-rush fare/min
WITH pairs AS (
    SELECT pz."Borough" pu_b, dz."Borough" do_b, f.is_rush_hour,
           AVG(f.total_amount/NULLIF(f.duration_min,0)) usd_per_min, COUNT(*) trips
    FROM fact_trips f
    JOIN dim_zone pz ON pz."LocationID"=f."PULocationID"
    JOIN dim_zone dz ON dz."LocationID"=f."DOLocationID"
    WHERE f.duration_min > 2 AND f.total_amount > 0
    GROUP BY 1,2,3 HAVING COUNT(*) > 10000
)
SELECT pu_b, do_b,
       ROUND(MAX(CASE WHEN is_rush_hour THEN usd_per_min END),2) rush_usd_per_min,
       ROUND(MAX(CASE WHEN NOT is_rush_hour THEN usd_per_min END),2) offrush_usd_per_min
FROM pairs GROUP BY 1,2 ORDER BY 1,2 LIMIT 12;

-- Q4. Airport economics: JFK/LaGuardia/EWR vs city average
SELECT CASE WHEN z."Zone" IN ('JFK Airport','LaGuardia Airport','Newark Airport')
            THEN z."Zone" ELSE 'All other zones' END AS pickup_segment,
       COUNT(*) trips, ROUND(AVG(f.trip_distance),1) avg_miles,
       ROUND(AVG(f.total_amount),2) avg_total,
       ROUND(100.0*AVG(f.tip_pct),1) avg_tip_pct
FROM fact_trips f JOIN dim_zone z ON z."LocationID"=f."PULocationID"
WHERE f.fare_amount >= 2.50 AND f.tip_pct <= 1 AND f.payment_type=1
GROUP BY 1 ORDER BY trips DESC;

-- Q5. Congestion-surcharge zones: share of trips paying it, avg amount
SELECT z."Borough", COUNT(*) trips,
       ROUND(100.0*AVG((f.congestion_surcharge > 0)::INT),1) pct_paying_surcharge,
       ROUND(AVG(CASE WHEN f.congestion_surcharge > 0 THEN f.congestion_surcharge END),2) avg_surcharge
FROM fact_trips f JOIN dim_zone z ON z."LocationID"=f."PULocationID"
GROUP BY 1 ORDER BY trips DESC;

-- Q6. Zone growth ranking: June vs January trip change, top risers/fallers
WITH mz AS (
    SELECT "PULocationID",
           SUM(CASE WHEN MONTH(pickup_datetime)=1 THEN 1 ELSE 0 END) jan,
           SUM(CASE WHEN MONTH(pickup_datetime)=6 THEN 1 ELSE 0 END) jun
    FROM fact_trips GROUP BY 1
)
SELECT z."Zone", jan, jun, ROUND(100.0*(jun-jan)/jan,1) growth_pct,
       RANK() OVER (ORDER BY 100.0*(jun-jan)/jan DESC) growth_rank
FROM mz JOIN dim_zone z ON z."LocationID"=mz."PULocationID"
WHERE jan > 5000 ORDER BY growth_pct DESC LIMIT 10;

-- Q7. Revenue concentration: top 10 zones' share of total revenue
WITH zr AS (
    SELECT "PULocationID", SUM(total_amount) rev
    FROM fact_trips GROUP BY 1
)
SELECT ROUND(100.0*SUM(rev) FILTER (rnk<=10)/SUM(rev),1) AS top10_zone_revenue_pct,
       ROUND(100.0*SUM(rev) FILTER (rnk<=50)/SUM(rev),1) AS top50_zone_revenue_pct
FROM (SELECT rev, RANK() OVER (ORDER BY rev DESC) rnk FROM zr);

-- Q8. Trip-speed distribution by hour (traffic curve), Manhattan pickups
SELECT f.hour_of_day, COUNT(*) trips,
       ROUND(AVG(f.speed_mph),1) avg_speed_mph,
       ROUND(MEDIAN(f.speed_mph),1) median_speed_mph
FROM fact_trips f JOIN dim_zone z ON z."LocationID"=f."PULocationID"
WHERE z."Borough"='Manhattan' AND f.speed_mph BETWEEN 0.5 AND 65
GROUP BY 1 ORDER BY 1;

-- Q9. Payment-mix shift by month (pivot)
SELECT strftime(pickup_datetime,'%Y-%m') AS month,
       ROUND(100.0*SUM(payment_type=1::INT)/COUNT(*),1) card_pct,
       ROUND(100.0*SUM(payment_type=2::INT)/COUNT(*),1) cash_pct
FROM fact_trips GROUP BY 1 ORDER BY 1;

-- Q10. Late-night demand (00:00-05:00) by borough and weekday/weekend
SELECT z."Borough", (f.day_of_week >= 5) AS weekend, COUNT(*) late_night_trips,
       ROUND(AVG(f.total_amount),2) avg_total
FROM fact_trips f JOIN dim_zone z ON z."LocationID"=f."PULocationID"
WHERE f.hour_of_day < 5
GROUP BY 1,2 ORDER BY 3 DESC;
