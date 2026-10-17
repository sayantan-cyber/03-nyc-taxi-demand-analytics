-- 01_star_schema.sql - DuckDB 1.5, executes on the raw parquet files.
-- Builds the star schema used by every downstream query and by Power BI.
-- __FILES__ and __ZONES__ are substituted by the pipeline with the local paths.

CREATE OR REPLACE TABLE dim_zone AS
SELECT "LocationID", "Borough", "Zone", "service_zone" FROM '__ZONES__';

CREATE OR REPLACE TABLE dim_payment_type AS
SELECT * FROM (VALUES
    (0,'Flex Fare trip'),(1,'Credit card'),(2,'Cash'),
    (3,'No charge'),(4,'Dispute'),(5,'Unknown'),(6,'Voided trip'))
AS t(payment_type, payment_name);

CREATE OR REPLACE TABLE dim_ratecode AS
SELECT * FROM (VALUES
    (1,'Standard rate'),(2,'JFK'),(3,'Newark'),(4,'Nassau or Westchester'),
    (5,'Negotiated fare'),(6,'Group ride'),(99,'Unknown'))
AS t("RatecodeID", rate_name);

CREATE OR REPLACE TABLE dim_date AS
SELECT d::DATE AS date,
       YEAR(d) AS year, MONTH(d) AS month, DAY(d) AS day,
       DAYOFWEEK(d) AS dow_iso, DAYNAME(d) AS day_name,
       (DAYOFWEEK(d) >= 5) AS is_weekend,
       strftime(d, '%Y-%m') AS year_month
FROM (SELECT UNNEST(generate_series(DATE '2023-01-01', DATE '2023-06-30', INTERVAL 1 DAY)) AS d);
-- hour_of_day lives on the fact (pickup hour); day_of_week view below keeps the matrix query simple.

CREATE OR REPLACE TABLE fact_trips AS
SELECT
    tpep_pickup_datetime::DATE                  AS pickup_date,
    tpep_pickup_datetime                        AS pickup_datetime,
    tpep_dropoff_datetime                       AS dropoff_datetime,
    "PULocationID", "DOLocationID",
    payment_type::INT                           AS payment_type,
    "RatecodeID"::INT                           AS "RatecodeID",
    "VendorID"::INT                             AS "VendorID",
    passenger_count, trip_distance,
    fare_amount, tip_amount, congestion_surcharge, total_amount,
    -- engineered features
    EPOCH(tpep_dropoff_datetime - tpep_pickup_datetime)/60.0 AS duration_min,
    trip_distance / NULLIF(EPOCH(tpep_dropoff_datetime - tpep_pickup_datetime)/3600.0, 0) AS speed_mph,
    CASE WHEN fare_amount > 0 THEN tip_amount / fare_amount END AS tip_pct,
    HOUR(tpep_pickup_datetime) AS hour_of_day,
    DAYOFWEEK(tpep_pickup_datetime::DATE) AS day_of_week,
    (HOUR(tpep_pickup_datetime) IN (7,8,9,16,17,18,19)
        AND DAYOFWEEK(tpep_pickup_datetime::DATE) < 5) AS is_rush_hour
FROM '__FILES__'
WHERE tpep_pickup_datetime >= '2023-01-01' AND tpep_pickup_datetime < '2023-07-01';
