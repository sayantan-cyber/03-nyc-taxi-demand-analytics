# Power BI star schema guide

Grain of fact_trips: one yellow-taxi trip (19.5M rows). For Power BI,
import the aggregated exports in data-exports/ (small, fast), or connect to
the fact table with DirectQuery/aggregation tables - do not import 19.5M
rows into an .pbix on a laptop.

## Relationships (all many-to-one, single direction)

    fact_trips[pickup_date]    -> dim_date[date]        (1:*)
    fact_trips[PULocationID]   -> dim_zone[LocationID]  (1:*)
    fact_trips[DOLocationID]   -> dim_zone[LocationID]  (1:*, second role -
                                 mark inactive, use USERELATIONSHIP for dropoff views)
    fact_trips[payment_type]   -> dim_payment_type[payment_type] (1:*)
    fact_trips[RatecodeID]     -> dim_ratecode[RatecodeID]       (1:*)

Snowflake is unnecessary: zones carry their borough denormalized.
Mark dim_date as a Date table for time-intelligence functions.

## Suggested pages

1. Demand: weekday x hour matrix (matrix visual), monthly trend (column).
2. Geography: top zones (bar), borough flow (sankey or chord).
3. Economics: tip % by payment (bar), distance bands (line+column combo).
4. Forecast: actual vs forecast June line (from forecast_june.csv).
