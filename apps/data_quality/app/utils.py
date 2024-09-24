import os
from datetime import datetime

from google.cloud import storage

ENV_SHORT_NAME = os.environ.get("ENV_SHORT_NAME", "dev")
DATA_BUCKET_NAME = f"data-bucket-{ENV_SHORT_NAME}"
yyyy = datetime.now().year
file_prefix = f"elementary_reports/{yyyy}"

storage_client = storage.Client()


def download_blob(bucket_name, source_blob_name):
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(source_blob_name)

    return blob.download_as_bytes()


def get_latest_file(bucket_name):
    bucket = storage_client.bucket(bucket_name)

    latest_file = None
    latest_date = None

    for blob in bucket.list_blobs(prefix=file_prefix):
        filename = blob.name
        try:
            date_str = filename.replace(".html", "")[-8:]
            file_date = datetime.strptime(date_str, "%Y%m%d")
            if latest_date is None or file_date > latest_date:
                latest_date = file_date
                latest_file = filename
        except ValueError:
            continue

    return latest_file
