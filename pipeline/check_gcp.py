"""Check that Python can reach GCS and BigQuery with the local credentials.

Run from the project root:
    python -m pipeline.check_gcp

Each step depends on the previous one, so the first failure tells where the problem is.
Nothing is created, changed or billed: listing a bucket is a free-tier operation and the
BigQuery query is a dry run (estimated, never executed).
"""

import google.auth
from google.cloud import bigquery, storage

from pipeline.config import CONFIG

GCP = CONFIG["gcp"]


def main() -> None:
    # 1. Credentials: google.auth looks for Application Default Credentials
    #    (created by `gcloud auth application-default login`).
    credentials, _ = google.auth.default()
    identity = getattr(credentials, "service_account_email", None) or type(credentials).__name__
    print(f"1. credentials found: {identity}")

    # 2. Storage: open the bucket and list what is inside.
    gcs = storage.Client(project=GCP["project_id"])
    bucket = gcs.bucket(GCP["bucket"])
    blobs = list(gcs.list_blobs(bucket, max_results=10))
    print(f"2. bucket gs://{bucket.name}: {len(blobs)} object(s) listed")

    # Bucket metadata (e.g. its region) is not checked here: roles/storage.objectAdmin
    # covers objects, not the bucket itself (storage.buckets.get is denied). The pipeline
    # never needs it, so the service account does not get it. Least privilege.

    # 3. BigQuery: a dry run validates the query and the permission to run jobs,
    #    and returns how many bytes it would read, without running it.
    bq = bigquery.Client(project=GCP["project_id"], location=GCP["region"])
    job = bq.query("SELECT 1 AS ok", job_config=bigquery.QueryJobConfig(dry_run=True))
    print(f"3. BigQuery dry run ok: would process {job.total_bytes_processed} bytes")

    print("All checks passed.")


if __name__ == "__main__":
    main()
