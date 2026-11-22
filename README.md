# NYC Taxi & Limousine data engineering study

A learning project built on the public [NYC TLC Trip Record Data](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page).

## Goal

Go through a full data engineering path with a dataset that does not fit in memory:

1. Local exploration with pandas: memory usage, data quality EDA
2. Data larger than RAM: pandas vs Polars vs DuckDB
3. Ingestion into Google Cloud Storage and BigQuery external tables
4. dbt staging models with tests
5. Kimball star schema (facts and dimensions)
6. Dashboards
7. Orchestration with Airflow

**Status:** steps 1 to 4 done (v0.4.0). See [CHANGELOG.md](CHANGELOG.md).

## Notebooks

| Notebook | What it does |
|---|---|
| `01_memory_analysis.ipynb` | Memory usage of FHVHV in pandas and dtype optimization |
| `02_eda_quality.ipynb` | Data quality checks and proposed dbt rules |
| `02b_eda_auto.ipynb` | Automatic EDA reports with Sweetviz (saved to `reports/`) |
| `03_benchmark.ipynb` | pandas vs Polars vs DuckDB on all 24 FHVHV months (483M rows): time, peak memory, threads |
| `04_bigquery.ipynb` | BigQuery external table over GCS: schema drift, what drives cost, bytes-billed cap, same query as DuckDB (bills ~34 GB per run) |

The benchmark query itself is in `benchmarks/fhvhv_aggregate.py`, run once per engine in a separate process.

## Data

Not versioned (about 12 GB). Download into a `datasets/` folder:

- Trip records (Parquet, monthly), 2024 and 2025: `yellow`, `green`, `fhv`, `fhvhv`
  `https://d37ci6vzurychx.cloudfront.net/trip-data/<type>_tripdata_<YYYY-MM>.parquet`
- Taxi Zone Lookup: `taxi_zone_lookup.csv`, from the same TLC page

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
nbstripout --install --attributes .gitattributes
```

Run the notebooks with the `.venv` kernel.

## Google Cloud setup

Values (project, region, bucket, datasets) live in `config.toml`. Code authenticates as a service account
through **impersonation**, so no key file is ever downloaded:

1. Install the Google Cloud CLI and run `gcloud init`
2. Enable the APIs: `storage`, `bigquery`, `iam`, `iamcredentials`
3. Create the service account `tlc-pipeline` with `roles/storage.objectAdmin`, `roles/bigquery.dataEditor` and `roles/bigquery.jobUser`
4. Give your user `roles/iam.serviceAccountTokenCreator` on that service account
5. Create local credentials that impersonate it:
   ```bash
   gcloud auth application-default login --impersonate-service-account tlc-pipeline@<project>.iam.gserviceaccount.com
   ```
6. Check the connection: `python -m pipeline.check_gcp`
7. After uploading, create the BigQuery external table: `python -m pipeline.create_raw_tables fhvhv`

## Upload to GCS

```bash
python -m pipeline.upload_to_gcs fhvhv --months 2025-01 --dry-run   # preview
python -m pipeline.upload_to_gcs fhvhv                              # every month found locally
```

Files land in hive-partitioned paths (`fhvhv/year=2025/month=01/...`). The script is idempotent:
files whose CRC32C checksum already matches the bucket are skipped.

## dbt

The dbt project lives in `dbt/` and connects to BigQuery with the same impersonated credentials
(`method: oauth` in `dbt/profiles.yml`, so no key file). Run every command from the `dbt/` folder:

```bash
cd dbt
dbt debug                                    # check the connection
dbt seed                                     # load seeds/taxi_zone_lookup.csv into staging.taxi_zone_lookup
dbt build --exclude fct_trips                # staging view + dimensions, with their tests
dbt build --select fct_trips --vars "{year: 2024, month: 1}"   # load one month of the fact table
dbt test --select "test_name:accepted_range" # run only the range tests
```

`fct_trips` needs `--vars` (see [Star schema](#star-schema)), so a plain `dbt run` or `dbt build` stops with
"Required var 'year' not found": exclude it or pass the month.

| Layer | Dataset | Contents |
|---|---|---|
| raw | `raw` | `fhvhv_trips`: external table over the Parquet files in GCS (source) |
| staging | `staging` | `stg_fhvhv_trips` view: renamed columns, `company` from the license number, Y/N flags as booleans, `cbd_congestion_fee` = 0 before 2025. No rows removed. `taxi_zone_lookup` seed |
| marts | `marts` | Star schema: `fct_trips`, `dim_zone`, `dim_date`, `dim_company` (tables) |
| test failures | `dbt_test__audit` | Failing rows of the range tests (`fare_out_of_range`, `driver_pay_out_of_range`), replaced on every run |

Datasets use the `+schema` name exactly as written (`marts`, not dbt's default `staging_marts`), thanks to
`dbt/macros/generate_schema_name.sql`.

**Tests and cost.** A test is a query that returns the rows breaking a rule. On the external table each
test reads its column across all 24 months, so `dbt test` bills about 20 GB of the free tier. Partition
columns (`partition_year`, `partition_month`) come from the folder names and cost nothing to read.
`accepted_range` is a custom generic test in `dbt/tests/generic/`. Negative fares and driver pay (a few
thousand rows per month) are reported as warnings; the fact table keeps them, flagged.

## Star schema

Kimball design for the High Volume FHV trips, in the `marts` dataset:

```
                 dim_date
                    │ pickup_date
dim_zone ──── fct_trips ──── dim_company
   (pickup and dropoff zone)   (license_number)
```

| Table | Grain | Rows | Built from |
|---|---|---|---|
| `fct_trips` | one trip | ~20M per month | `stg_fhvhv_trips`, one month per run |
| `dim_zone` | one TLC zone | 265 | `taxi_zone_lookup` seed. Used twice by the fact (role-playing) |
| `dim_date` | one day | 731 (2024-2025) | generated in SQL |
| `dim_company` | one HVFHS license | 4 | written in SQL (Juno, Uber, Via, Lyft) |

The fact holds only keys, timestamps, measures (miles, duration, fare, fees, tips, driver pay) and flags.
Descriptive attributes live in the dimensions. Negative fares (likely refunds or adjustments) are kept and
flagged with `is_negative_fare`.

**Loading `fct_trips`.** It is an incremental model partitioned by `pickup_date` (one partition per day)
and clustered by `license_number` and `pickup_location_id`. Each run loads one month:

```bash
dbt build --select fct_trips --vars "{year: 2024, month: 3}"
```

- The month filter on `partition_year` / `partition_month` always applies, so BigQuery opens only that
  month's file: **~2.9 GB billed per month**.
- `insert_overwrite` replaces that month's days, so re-running a month does not duplicate rows.
- `copy_partitions` moves the new days in with free copy jobs instead of a `MERGE` (which doubled the cost).
- With `--vars`, the 8 tests (`not_null`, `relationships` to each dimension) only check that month:
  ~0.3 GB per test no matter how many months are loaded.
- **Do not use `--full-refresh`** unless the columns change: it rebuilds the table with only the month
  passed in `--vars`, so every month must be loaded again afterwards.

| Months loaded | Storage | Monthly storage cost |
|---|---|---|
| 2 (current) | ~5.9 GB | free (10 GiB free tier) |
| 24 | ~71 GB | ~US$1.10, ~US$0.55 after 90 days unchanged (long-term) |

## Delete and rebuild

Processing fits the free tier (1 TiB of queries per month), storage does not: the GCS files (~11 GB, 5 GB
free) and a full `fct_trips` (~71 GB, 10 GiB free) cost a little every day. Everything can be rebuilt from
the public TLC files and this repository, so delete what costs when the project is paused.

The commands below use your own `gcloud` account. `bq rm` asks for confirmation before deleting.

**Pause (delete what costs, keep everything else):**

```bash
bq rm -t nyc-tlc-de-4821:marts.fct_trips                  # the fact table
gcloud storage rm --recursive gs://nyc-tlc-de-4821-raw/fhvhv  # the Parquet files (the empty bucket is free)
```

The dimensions, views and external table stay (they cost nothing). Queries on `raw` and `staging` fail
until the files are uploaded again.

**Full teardown (end of the project):**

```bash
bq rm -r -d nyc-tlc-de-4821:marts
bq rm -r -d nyc-tlc-de-4821:dbt_test__audit
bq rm -r -d nyc-tlc-de-4821:staging_dbt_test__audit       # old name of the test failures dataset
bq rm -r -d nyc-tlc-de-4821:staging
bq rm -r -d nyc-tlc-de-4821:raw
gcloud storage rm --recursive gs://nyc-tlc-de-4821-raw     # files and bucket
```

**Rebuild** (in this order, from the project root; the files must be in `datasets/`, see [Data](#data)):

| Step | Command | Needed after | Billed |
|---|---|---|---|
| 1. Recreate the bucket | `gcloud storage buckets create gs://nyc-tlc-de-4821-raw --location=us-central1` | teardown | free |
| 2. Upload the files | `python -m pipeline.upload_to_gcs fhvhv` | pause, teardown | free (upload) |
| 3. External table | `python -m pipeline.create_raw_tables fhvhv` | teardown | free |
| 4. Seed, views and dimensions | `cd dbt` then `dbt seed` and `dbt run --exclude fct_trips` | teardown | a few MB |
| 5. Fact table, one month per run | `dbt build --select fct_trips --vars "{year: 2024, month: 1}"` | pause, teardown | ~2.9 GB + ~1 GB of tests per month |

To load several months, loop in PowerShell (here the first quarter of 2024):

```powershell
foreach ($m in 1..3) { dbt build --select fct_trips --vars "{year: 2024, month: $m}" }
```

A full rebuild of 24 months bills about 100 GB of queries, inside the free tier.
