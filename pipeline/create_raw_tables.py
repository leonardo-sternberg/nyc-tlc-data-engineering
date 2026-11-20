"""Create the BigQuery `raw` dataset and one external table per TLC dataset found in the bucket.

An external table stores no data: only a definition pointing at the Parquet files in GCS.
Creating it is free and instant; queries read the files at query time.

Usage (from the project root):
    python -m pipeline.create_raw_tables fhvhv

Safe to re-run: the dataset is created only if missing and the table is replaced
(CREATE OR REPLACE), which only rewrites the definition, never the files.
"""

import argparse

from google.cloud import bigquery

from pipeline.config import CONFIG

DATASETS = ["yellow", "green", "fhv", "fhvhv"]


def create_dataset(client: bigquery.Client, name: str, location: str) -> None:
    dataset = bigquery.Dataset(f"{client.project}.{name}")
    dataset.location = location  # must be compatible with the bucket's location
    dataset.description = "Raw TLC data, exactly as published. External tables over GCS. Never modified."
    client.create_dataset(dataset, exists_ok=True)
    print(f"dataset {client.project}.{name} ready ({location})")


def create_external_table(client: bigquery.Client, raw_dataset: str, bucket: str, tlc_dataset: str) -> None:
    prefix = f"gs://{bucket}/{tlc_dataset}"
    table = f"`{client.project}.{raw_dataset}.{tlc_dataset}_trips`"
    sql = f"""
        CREATE OR REPLACE EXTERNAL TABLE {table}
        WITH PARTITION COLUMNS (year INT64, month INT64)
        OPTIONS (
            format = 'PARQUET',
            uris = ['{prefix}/*'],
            hive_partition_uri_prefix = '{prefix}',
            require_hive_partition_filter = FALSE
        )
    """
    print(sql)
    job = client.query(sql)
    job.result()  # wait for the DDL to finish
    print(f"table {table} ready, {job.total_bytes_processed or 0} bytes processed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("tlc_dataset", choices=DATASETS)
    args = parser.parse_args()

    gcp, bq_cfg = CONFIG["gcp"], CONFIG["bigquery"]
    client = bigquery.Client(project=gcp["project_id"], location=gcp["region"])
    create_dataset(client, bq_cfg["raw_dataset"], gcp["region"])
    create_external_table(client, bq_cfg["raw_dataset"], gcp["bucket"], args.tlc_dataset)


if __name__ == "__main__":
    main()
