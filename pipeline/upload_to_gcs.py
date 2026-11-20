"""Upload TLC Parquet files from datasets/ to the GCS bucket, in hive-partitioned paths.

    datasets/fhvhv_tripdata_2025-01.parquet
      -> gs://<bucket>/fhvhv/year=2025/month=01/fhvhv_tripdata_2025-01.parquet

The `year=` / `month=` folders are "hive partitioning": BigQuery (and DuckDB, Spark...)
turn them into columns and can skip whole folders when a query filters on them.

Idempotent: a file whose CRC32C checksum already matches the object in the bucket
is skipped, so the script can be re-run safely (e.g. after a failure halfway).

Usage (from the project root):
    python -m pipeline.upload_to_gcs fhvhv --months 2025-01 --dry-run
    python -m pipeline.upload_to_gcs fhvhv --months 2025-01 2025-02
    python -m pipeline.upload_to_gcs fhvhv            # every month found locally
"""

import argparse
import base64
import re
import time
from pathlib import Path

import google_crc32c
from google.cloud import storage

from pipeline.config import CONFIG, ROOT

DATASETS = ["yellow", "green", "fhv", "fhvhv"]
FILE_PATTERN = re.compile(r"(?P<dataset>\w+?)_tripdata_(?P<year>\d{4})-(?P<month>\d{2})\.parquet")
CHUNK = 8 * 1024 * 1024  # read files in 8 MB pieces to compute checksums without loading them


def object_name(path: Path) -> str:
    """datasets/fhvhv_tripdata_2025-01.parquet -> fhvhv/year=2025/month=01/fhvhv_tripdata_2025-01.parquet"""
    m = FILE_PATTERN.fullmatch(path.name)
    return f"{m['dataset']}/year={m['year']}/month={m['month']}/{path.name}"


def crc32c_b64(path: Path) -> str:
    """CRC32C of a local file, base64-encoded: the same format GCS stores in blob.crc32c."""
    checksum = google_crc32c.Checksum()
    with open(path, "rb") as f:
        while chunk := f.read(CHUNK):
            checksum.update(chunk)
    return base64.b64encode(checksum.digest()).decode()


def month_of(path: Path) -> str:
    """datasets/fhvhv_tripdata_2025-01.parquet -> "2025-01" """
    m = FILE_PATTERN.fullmatch(path.name)
    return f"{m['year']}-{m['month']}"


def local_files(dataset: str, months: list[str] | None) -> list[Path]:
    datasets_dir = ROOT / CONFIG["local"]["datasets_dir"]
    files = sorted(datasets_dir.glob(f"{dataset}_tripdata_*.parquet"))
    if months:
        files = [f for f in files if month_of(f) in months]
        missing = set(months) - {month_of(f) for f in files}
        if missing:
            raise SystemExit(f"Not found locally: {sorted(missing)}")
    return files


def upload(dataset: str, months: list[str] | None, dry_run: bool) -> None:
    gcp = CONFIG["gcp"]
    client = storage.Client(project=gcp["project_id"])
    bucket = client.bucket(gcp["bucket"])

    files = local_files(dataset, months)
    total_mb = sum(f.stat().st_size for f in files) / 1e6
    print(f"{len(files)} file(s), {total_mb:,.0f} MB -> gs://{bucket.name}/{dataset}/  {'(dry run)' if dry_run else ''}")

    uploaded = skipped = 0
    for path in files:
        name = object_name(path)
        local_crc = crc32c_b64(path)
        blob = bucket.get_blob(name)  # None if the object does not exist

        if blob is not None and blob.crc32c == local_crc:
            print(f"  skip   {name} (same checksum already in bucket)")
            skipped += 1
            continue

        action = "replace" if blob is not None else "upload"
        size_mb = path.stat().st_size / 1e6
        if dry_run:
            print(f"  {action:7s}{name} ({size_mb:,.0f} MB)")
            continue

        start = time.perf_counter()
        new_blob = bucket.blob(name)
        new_blob.upload_from_filename(
            path,
            checksum="crc32c",  # GCS recomputes it on arrival and rejects a corrupted upload
            timeout=3600,       # default is 60 s per request: too short for 500 MB on a home connection
            # Preconditions: only create if absent, or only replace the exact version we saw.
            # Protects against two runs writing the same object at the same time.
            if_generation_match=blob.generation if blob is not None else 0,
        )
        seconds = time.perf_counter() - start
        print(f"  {action:7s}{name} ({size_mb:,.0f} MB in {seconds:,.0f} s, {size_mb / seconds:,.1f} MB/s)")
        uploaded += 1

    print(f"Done: {uploaded} uploaded, {skipped} skipped" + (" (dry run, nothing sent)" if dry_run else ""))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("dataset", choices=DATASETS)
    parser.add_argument("--months", nargs="+", metavar="YYYY-MM", help="default: every month found locally")
    parser.add_argument("--dry-run", action="store_true", help="show what would be uploaded, send nothing")
    args = parser.parse_args()
    upload(args.dataset, args.months, args.dry_run)


if __name__ == "__main__":
    main()
