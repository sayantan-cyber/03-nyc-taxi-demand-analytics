# Data

The raw trip files are NOT committed to this repository (319 MB of parquet).
To reproduce every number, download exactly these files:

## NYC TLC Yellow Taxi Trip Records, Jan-Jun 2023

Official source (NYC Taxi & Limousine Commission):
https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page

Direct parquet links used for this analysis (all re-verified live 17 Oct 2026):

    cd data
    for m in 01 02 03 04 05 06; do
      curl -O https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2023-$m.parquet
    done
    curl -O https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv

Expected downloads (byte sizes at download time):

    yellow_tripdata_2023-01.parquet   47,673,370 bytes
    yellow_tripdata_2023-02.parquet   47,748,012
    yellow_tripdata_2023-03.parquet   56,127,762
    yellow_tripdata_2023-04.parquet   54,222,699
    yellow_tripdata_2023-05.parquet   58,654,627
    yellow_tripdata_2023-06.parquet   54,999,465
    taxi_zone_lookup.csv              12,331 bytes (265 zones)

Expected content, verified by the pipeline's validation checks:
19,493,620 total rows x 19 columns; in-window trips Jan-Jun 2023:
3,066,726 / 2,914,003 / 3,403,660 / 3,288,248 / 3,514,664* / 3,307,218 per month.
(* see validation_results.txt for the exact asserted values.)

The pipeline fails loudly if the files do not match these shapes, so a wrong
or corrupted download cannot silently produce numbers.

## Terms

NYC public data, published by the TLC under the city's open-data program
(Local Law 11 of 2012: public datasets are available without registration,
license or usage restrictions). Attribution: "Source: NYC Taxi & Limousine
Commission Trip Record Data". The TLC states the data was collected by
authorized technology vendors and that it "makes no representations as to
the accuracy of these data" - treat quality quirks as real, and see the
Limitations section of docs/findings_and_recommendations.md.
