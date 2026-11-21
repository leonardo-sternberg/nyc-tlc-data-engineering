# Changelog

Format based on [Keep a Changelog](https://keepachangelog.com/). Versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

dbt staging layer with tests.

### Added
- dbt project in `dbt/` (dbt-core 1.12.7, dbt-bigquery 1.12.4) connected to BigQuery through the impersonated credentials (`method: oauth`), with a bytes-billed cap
- `raw` source over the `raw.fhvhv_trips` external table
- `stg_fhvhv_trips` view: renamed columns, `company` derived from the license number, Y/N flags as booleans, `cbd_congestion_fee` = 0 before 2025. No rows removed
- Data tests: `accepted_values` (year, company), `not_null` (pickup/dropoff time, pickup zone)
- `accepted_range` custom generic test, used on fares and driver pay with `severity: warn`. Failing rows are stored with their year and month in `staging_dbt_test__audit`
- `taxi_zone_lookup` seed (265 zones) with `unique` and `not_null` tests on the id

## [0.3.0] - 2026-11-20

Google Cloud Storage and BigQuery external tables.

### Added
- `config.toml` + `pipeline.config`: project, region, bucket and BigQuery settings in one place
- `pipeline.check_gcp`: checks credentials, bucket access and BigQuery as the `tlc-pipeline` service account
- `pipeline.upload_to_gcs`: idempotent upload (CRC32C) to hive-partitioned paths. All 24 FHVHV months are in the bucket
- `pipeline.create_raw_tables`: `raw` dataset and `raw.fhvhv_trips` external table
- `pipeline.bq`: query helper with a hard cap on bytes billed
- `04_bigquery.ipynb`: schema drift, what drives BigQuery cost, the bytes-billed cap, and the benchmark query compared with DuckDB
- Google Cloud libraries and `db-dtypes` in requirements; GCP setup in the README

## [0.2.0] - 2026-11-20

Data larger than RAM: pandas vs Polars vs DuckDB.

### Added
- `03_benchmark.ipynb` and `benchmarks/fhvhv_aggregate.py`: the same aggregation over all 24 FHVHV months (483M rows) with pandas, Polars and DuckDB. Measures time and peak memory, with all threads and with one thread, and checks that the results match
- `psutil` in requirements (peak memory measurement)

## [0.1.0] - 2026-11-20

Local exploration with pandas.

### Added
- `01_memory_analysis.ipynb`: RAM per column for one FHVHV month, pandas backends, dtype optimization (2.4x smaller), projection for 2024 + 2025
- `02_eda_quality.ipynb`: 28 data quality checks on one FHVHV month, with findings mapped to dbt staging rules
- `02b_eda_auto.ipynb`: automatic EDA with Sweetviz (one month, Uber vs Lyft, 2025 vs 2024)
- Project setup: README, pinned requirements, `.gitignore`, nbstripout filter, `CLAUDE.md`
