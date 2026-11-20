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

**Status:** step 1 done (v0.1.0). See [CHANGELOG.md](CHANGELOG.md).

## Notebooks

| Notebook | What it does |
|---|---|
| `01_memory_analysis.ipynb` | Memory usage of FHVHV in pandas and dtype optimization |
| `02_eda_quality.ipynb` | Data quality checks and proposed dbt rules |
| `02b_eda_auto.ipynb` | Automatic EDA reports with Sweetviz (saved to `reports/`) |
| `03_benchmark.ipynb` | pandas vs Polars vs DuckDB on all 24 FHVHV months (483M rows): time, peak memory, threads |

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
