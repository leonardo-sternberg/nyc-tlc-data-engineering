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

**Status:** steps 1 to 3 done (v0.3.0). See [CHANGELOG.md](CHANGELOG.md).

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
dbt run                                      # build the staging views
dbt test                                     # run all data tests (bills ~20 GB, see below)
dbt build --select stg_fhvhv_trips           # run + test one model
dbt test --select "test_name:accepted_range" # run only the range tests
```

| Layer | Dataset | Contents |
|---|---|---|
| raw | `raw` | `fhvhv_trips`: external table over the Parquet files in GCS (source) |
| staging | `staging` | `stg_fhvhv_trips` view: renamed columns, `company` from the license number, Y/N flags as booleans, `cbd_congestion_fee` = 0 before 2025. No rows removed. `taxi_zone_lookup` seed |
| test failures | `staging_dbt_test__audit` | Failing rows of the range tests (`fare_out_of_range`, `driver_pay_out_of_range`), replaced on every run |

**Tests and cost.** A test is a query that returns the rows breaking a rule. On the external table each
test reads its column across all 24 months, so `dbt test` bills about 20 GB of the free tier. Partition
columns (`partition_year`, `partition_month`) come from the folder names and cost nothing to read.
`accepted_range` is a custom generic test in `dbt/tests/generic/`. Negative fares and driver pay (a few
thousand rows per month) are reported as warnings until the star schema decides how to treat them.
