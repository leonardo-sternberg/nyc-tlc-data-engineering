"""Small BigQuery helpers that always apply a cost cap.

    from pipeline.bq import client, query
    df = query("SELECT ... FROM raw.fhvhv_trips WHERE year = 2025 AND month = 1")

Every query runs with `maximum_bytes_billed`: if it would bill more than the cap,
BigQuery refuses it before reading anything and nothing is charged.
"""

import time
from dataclasses import dataclass

import pandas as pd
from google.cloud import bigquery

from pipeline.config import CONFIG

DEFAULT_MAX_GB = CONFIG["bigquery"]["max_gb_billed_per_query"]


def client() -> bigquery.Client:
    gcp = CONFIG["gcp"]
    return bigquery.Client(project=gcp["project_id"], location=gcp["region"])


@dataclass
class QueryStats:
    gb_processed: float
    gb_billed: float
    seconds: float


def dry_run_gb(sql: str) -> float:
    """Estimated GB without running. Note: always 0 for external tables (data lives outside BigQuery)."""
    job = client().query(sql, job_config=bigquery.QueryJobConfig(dry_run=True, use_query_cache=False))
    return job.total_bytes_processed / 1e9


def query(sql: str, max_gb: float = DEFAULT_MAX_GB, verbose: bool = True) -> pd.DataFrame:
    """Run a query with a hard cap on bytes billed. Prints GB billed and time."""
    cfg = bigquery.QueryJobConfig(maximum_bytes_billed=int(max_gb * 1e9), use_query_cache=False)
    start = time.perf_counter()
    job = client().query(sql, job_config=cfg)
    df = job.result().to_dataframe()
    stats = QueryStats(
        gb_processed=(job.total_bytes_processed or 0) / 1e9,
        gb_billed=(job.total_bytes_billed or 0) / 1e9,
        seconds=time.perf_counter() - start,
    )
    df.attrs["stats"] = stats
    if verbose:
        print(f"billed {stats.gb_billed:.3f} GB | processed {stats.gb_processed:.3f} GB | {stats.seconds:.1f} s")
    return df
