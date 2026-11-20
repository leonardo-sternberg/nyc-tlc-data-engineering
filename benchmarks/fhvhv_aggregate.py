"""Run one aggregation over all FHVHV files with one engine and report time and peak memory.

The query: trips, miles, trip time, fare and driver pay per pickup month and company.

Each engine runs in its own process (this script), so the peak memory of one engine
does not leak into the measurement of another.

Usage:
    python benchmarks/fhvhv_aggregate.py <engine> <datasets_dir> <output.parquet>

engine: pandas | polars | duckdb

Prints one JSON line: {"engine", "seconds", "peak_mb", "rows"}.

Optional: set BENCH_THREADS=N to limit DuckDB and Polars to N threads
(the caller must also set POLARS_MAX_THREADS=N, read by Polars at import time).
pandas is single-threaded either way.
"""

import json
import os
import sys
import time
from pathlib import Path

import psutil

COLUMNS = [
    "hvfhs_license_num",
    "pickup_datetime",
    "trip_miles",
    "trip_time",
    "base_passenger_fare",
    "driver_pay",
]
SUM_COLS = ["trip_miles", "trip_time", "base_passenger_fare", "driver_pay"]
GROUP_COLS = ["month", "hvfhs_license_num"]


def run_pandas(files: list[Path]):
    """Map-reduce by hand: aggregate each file, then aggregate the partial results.

    Only 6 of the 25 columns are read (projection), and only one file is in memory at a time.
    """
    import pandas as pd

    partials = []
    for f in files:
        df = pd.read_parquet(f, columns=COLUMNS)
        df["month"] = df["pickup_datetime"].dt.to_period("M").dt.to_timestamp()
        part = df.groupby(GROUP_COLS, observed=True).agg(
            trips=("trip_miles", "size"), **{c: (c, "sum") for c in SUM_COLS}
        )
        partials.append(part)
        del df

    # Sum the partials again in case the same group shows up in two files.
    # FHVHV 2024-2025 has no trip outside its file's month, but yellow taxi
    # files do (634 of 90M rows), so we do not rely on it. Sums and counts
    # can be re-aggregated like this; means and distinct counts cannot.
    result = pd.concat(partials).groupby(level=GROUP_COLS).sum().reset_index()
    return result


def run_polars(files: list[Path]):
    """Lazy query + streaming engine: Polars plans the whole query, then processes it in batches."""
    import polars as pl

    # Polars takes the schema from the first file (2024-01, no cbd_congestion_fee) and,
    # by default, rejects files with extra columns. We only select 6 columns anyway.
    lazy = (
        pl.scan_parquet(files, extra_columns="ignore")
        .select(COLUMNS)
        .group_by(pl.col("pickup_datetime").dt.truncate("1mo").alias("month"), "hvfhs_license_num")
        .agg(pl.len().alias("trips"), *[pl.col(c).sum() for c in SUM_COLS])
    )
    return lazy.collect(engine="streaming").to_pandas()


def run_duckdb(files: list[Path]):
    """SQL directly on the Parquet files. DuckDB streams them and spills to disk if needed."""
    import duckdb

    file_list = ", ".join(f"'{f.as_posix()}'" for f in files)
    sql = f"""
        SELECT
            date_trunc('month', pickup_datetime) AS month,
            hvfhs_license_num,
            count(*)                 AS trips,
            sum(trip_miles)          AS trip_miles,
            sum(trip_time)           AS trip_time,
            sum(base_passenger_fare) AS base_passenger_fare,
            sum(driver_pay)          AS driver_pay
        FROM read_parquet([{file_list}])
        GROUP BY ALL
    """
    con = duckdb.connect()
    if threads := os.environ.get("BENCH_THREADS"):
        con.execute(f"SET threads = {int(threads)}")
    return con.sql(sql).df()


ENGINES = {"pandas": run_pandas, "polars": run_polars, "duckdb": run_duckdb}


def peak_memory_mb() -> float:
    """Peak memory of this process since it started.

    Windows exposes the peak working set directly. Elsewhere, fall back to ru_maxrss.
    """
    info = psutil.Process().memory_info()
    if hasattr(info, "peak_wset"):
        return info.peak_wset / 1e6
    import resource

    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e3  # KB on Linux


def main() -> None:
    engine, datasets_dir, output = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    files = sorted(datasets_dir.glob("fhvhv_tripdata_*.parquet"))

    start = time.perf_counter()
    result = ENGINES[engine](files)
    seconds = time.perf_counter() - start

    result = result.sort_values(GROUP_COLS).reset_index(drop=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    result.to_parquet(output, index=False)

    print(json.dumps({
        "engine": engine,
        "seconds": round(seconds, 2),
        "peak_mb": round(peak_memory_mb()),
        "rows": len(result),
    }))


if __name__ == "__main__":
    main()
