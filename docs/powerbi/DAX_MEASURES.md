# DAX measures (copy-paste ready)

    Total Trips = COUNTROWS(fact_trips)

    Total Revenue = SUM(fact_trips[total_amount])

    Avg Fare per Mile =
    DIVIDE(SUM(fact_trips[fare_amount]), SUM(fact_trips[trip_distance]))

    Tip % (cards) =
    DIVIDE(
        CALCULATE(SUM(fact_trips[tip_amount]), fact_trips[payment_type] = 1),
        CALCULATE(SUM(fact_trips[fare_amount]), fact_trips[payment_type] = 1))

    Trips MA 7d =
    AVERAGEX(DATESINPERIOD(dim_date[date], MAX(dim_date[date]), -7, DAY),
             [Total Trips])

    DoD Growth % =
    VAR t = [Total Trips]
    VAR y = CALCULATE([Total Trips], PREVIOUSDAY(dim_date[date]))
    RETURN DIVIDE(t - y, y)

    Rush Hour Trips =
    CALCULATE([Total Trips], fact_trips[is_rush_hour] = TRUE())

    Dropoff Borough Trips =
    CALCULATE([Total Trips],
              USERELATIONSHIP(fact_trips[DOLocationID], dim_zone[LocationID]))

Notes: use DIVIDE (never /) for safe blanks; PREVIOUSDAY needs dim_date
marked as a Date table; keep the dropoff relationship inactive.
