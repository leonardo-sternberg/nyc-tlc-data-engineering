# Project context for Claude

## Purpose
A **learning project**. The owner wants to understand every step: explain what you are doing, how and why, show the commands you run, and explain errors and their fixes. Talk to the user in Portuguese; code, notebooks, docs and commit messages in English.

## Roadmap
1. Local exploration with pandas (done in v0.1.0)
2. Data larger than RAM: pandas vs Polars vs DuckDB on FHVHV 2024 + 2025 (done, `03_benchmark.ipynb`)
3. GCS + BigQuery external tables (done in v0.3.0, `04_bigquery.ipynb`)
4. dbt staging with tests (done in v0.4.0, project in `dbt/`)
5. Kimball star schema (done in v0.5.0, `dbt/models/marts/`)
6. Dashboards
7. Airflow orchestration
Optional later: Kafka → MinIO

## Environment
- Windows 11, 64 GB RAM, Python 3.14 in `.venv`, pandas 3.1 (strings are Arrow-backed by default)
- Run notebooks with the `.venv` kernel. The `python3` kernelspec calls `python` from PATH, so when executing with `nbconvert` from a shell, put `.venv/Scripts` first in PATH
- Some `.exe` entry points (e.g. `jupyter-kernelspec`) are blocked by Windows Application Control: use `python -m <module>` instead
- Data lives in `datasets/` (not versioned): yellow, green, fhv, fhvhv for 2024 and 2025 + `taxi_zone_lookup.csv`
- GCP: project `nyc-tlc-de-4821`, region `us-central1`, bucket `nyc-tlc-de-4821-raw` (all in `config.toml`, read via `pipeline.config.CONFIG`). The billing account is shared with other projects of the user
- Auth: Application Default Credentials impersonating `tlc-pipeline@...` (no key files). Its roles: `storage.objectAdmin`, `bigquery.dataEditor`, `bigquery.jobUser`. It **cannot read bucket metadata** (`storage.buckets.get`): do not call `bucket.reload()` in pipeline code
- Run pipeline code as modules from the project root: `python -m pipeline.<name>`
- Bucket content: `fhvhv/year=YYYY/month=MM/fhvhv_tripdata_YYYY-MM.parquet` for 2024-01..2025-12 (24 files, 11.7 GB), uploaded with `pipeline.upload_to_gcs` (idempotent, CRC32C). Upload speed from this machine: ~18–20 MB/s

## Git workflow
- **git-flow**, chosen to learn it: `main` (releases only, tagged `vX.Y.Z`), `develop`, `feature/*`, `release/*`, `hotfix/*`
- Merge with `--no-ff`; use plain git commands, not the `git flow` extension
- Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`, `refactor:`)
- Notebook outputs are stripped on commit by nbstripout (local copies keep them)

## Decisions and findings
- **Do not drop rows with nulls in FHVHV**: `on_scene_datetime` and `originating_base_num` are null for ~99.7% of Lyft trips (Lyft does not report them). Dropping nulls removes almost all Lyft data
- 2024 files have no `cbd_congestion_fee` (Manhattan congestion pricing started in January 2025). Code must tolerate the missing column
- Memory: one FHVHV month is 4.36 GB raw / 1.80 GB optimized (category for text, float32, int32/int16). FHVHV 2024 + 2025 ≈ 103 GB raw / 43 GB optimized
- Automatic EDA uses **Sweetviz**: ydata-profiling does not support Python 3.14 and skimpy breaks with pandas 3. Sweetviz needs text columns forced as categorical (`force_cat`) for comparisons
- Measure instead of estimating: earlier estimates of memory were wrong by 2–3x
- Benchmark (all 24 FHVHV months, 483M rows, one group-by): DuckDB ~2.2 s / 2.5 GB, Polars ~2.5 s / 2.5–6 GB (varies between runs), pandas ~101 s / 3.5 GB (6 columns, one file at a time). With 1 thread: DuckDB and Polars ~44 s; DuckDB peaks at 0.15 GB. **DuckDB is the tool for local heavy lifting** (SQL, like BigQuery and dbt)
- Polars `scan_parquet` over 2024 + 2025 needs `extra_columns="ignore"` (schema drift: `cbd_congestion_fee`)
- BigQuery: `raw.fhvhv_trips` is an external table (hive partitions `year`, `month` INT64), created by `pipeline.create_raw_tables`. 2024 rows return `cbd_congestion_fee` = NULL (dbt staging should coalesce to 0 before 2025)
- BigQuery cost: billed by **logical** bytes of the columns read (8 per number/timestamp, 2 + length per string), not Parquet size. Only `year`/`month` filters skip files; a `pickup_datetime` filter reads all 24. Dry run returns 0 for external tables
- Always query through `pipeline.bq.query` (applies `maximum_bytes_billed` from `config.toml`, default 30 GB). Verified: over the cap, BigQuery refuses and bills nothing
- Avoid re-running `04_bigquery.ipynb` casually: it bills ~34 GB of the 1 TiB monthly free tier
- Free-tier usage: query `region-us-central1`.INFORMATION_SCHEMA.JOBS_BY_PROJECT with `bq` (the user's account). The 1 TiB is per billing account, shared with the user's other projects

## dbt
- Pin `dbt-core` and `dbt-bigquery` (1.12.x): unpinned, pip pulls a 1.13 beta. Run dbt from `dbt/` with `..\.venv\Scripts\dbt.exe` if the venv is not active
- `profiles.yml` is in the project (no secrets: `method: oauth` uses ADC) with `maximum_bytes_billed` 30 GB
- Layers: `raw` (external tables, dbt sources) → `staging` (views, no rows removed) → marts (step 5, Kimball)
- Test syntax (1.12): `data_tests:`, test arguments under `arguments:`, test config (`severity`, `store_failures`, `alias`) under `config:`. Use `quote: false` for numeric `accepted_values`
- Every test on the external table reads its column over all 24 files: full `dbt test` bills ~20 GB. Select tests (`--select`) when only some changed. `not_null` can be cheaper when files carry null_count statistics
- Partition columns cost nothing (they come from the GCS path): verified, adding them to `extra_columns` did not change bytes billed
- Negative `base_passenger_fare` (31,728 rows, peak 8,512 in 2024-02) and `driver_pay` (2,743) exist, none above 5000. Kept in staging and reported as warnings. Decision for step 5: flag in staging, keep or filter in the fact table (likely refunds/adjustments)
- Run `dbt clean` when `target/` has stale compiled files from renamed tests

## Star schema (marts)
- `generate_schema_name` is overridden: `+schema: marts` gives dataset `marts`; test failures go to `dbt_test__audit`
- `fct_trips` needs `--vars "{year: YYYY, month: M}"` (no default on purpose): plain `dbt run`/`build` fails on it, use `--exclude fct_trips`. Loaded so far: 2024-01 and 2024-02 only (storage stays in the 10 GiB free tier)
- `insert_overwrite` alone bills the month twice (temp table + MERGE, 5.8 GB). `copy_partitions: true` replaces the MERGE with free copy jobs (2.9 GB, but ~1 copy job per day, slower)
- Never `--full-refresh` fct_trips casually: it rebuilds with only the month in `--vars`
- Test `where` filters: the filter column is billed too (relationships with the month filter = ~310 MB, two columns of one month). `not_null` on native tables billed 0 bytes (block metadata)
- Free row counts per month: `marts.INFORMATION_SCHEMA.PARTITIONS` (metadata, 0 bytes)
- Plan: after step 7, full GCP teardown (README "Delete and rebuild"). Free tiers are per billing account, shared with the user's other projects; GCS is already over its 5 GB free tier
