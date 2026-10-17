# Data dictionary (measured, not copied)

Source files: yellow_tripdata_2023-01..06.parquet (19 columns each),
taxi_zone_lookup.csv (265 rows x 4 columns).

## Raw trip columns (all 6 files)

| column | type | what it is | measured notes |
|---|---|---|---|
| VendorID | int | TPEP vendor (1/2) | - |
| tpep_pickup_datetime | timestamp | meter start | 0 nulls; 101 rows outside Jan-Jun 2023 |
| tpep_dropoff_datetime | timestamp | meter end | 0 nulls |
| passenger_count | float | driver-reported | 528,552 nulls (2.7%) |
| trip_distance | float | miles | 246,535 zero-distance rows with positive fare |
| RatecodeID | float | 1=standard..6=group | some 99s (unknown) |
| store_and_fwd_flag | str | Y/N vendor flag | - |
| PULocationID / DOLocationID | int | TLC zone ids | 100% coverage vs 265-zone lookup |
| payment_type | int | 1=card 2=cash 3=no-charge 4=dispute 0/5=unknown | 0 nulls |
| fare_amount, extra, mta_tax, tip_amount, tolls_amount, improvement_surcharge, congestion_surcharge, airport_fee, total_amount | float | USD components | 173,015 negative fares; tip_amount never set on cash |

## Star schema built by sql/01_star_schema.sql

- **fact_trips** (19,493,519 rows = in-window trips): dates/timestamps, zone
  ids, payment/rate/vendor ids, money fields, plus engineered features:
  duration_min, speed_mph, tip_pct (tip/fare when fare>0), hour_of_day,
  day_of_week, is_rush_hour (7-9h and 16-19h, Mon-Fri).
- **dim_zone** (265): LocationID, Borough, Zone, service_zone.
- **dim_date** (181): calendar attrs incl. is_weekend, year_month.
- **dim_payment_type** (7), **dim_ratecode** (7): decoded labels.
