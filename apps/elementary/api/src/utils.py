from datetime import datetime

from constants import GCP_PROJECT_ID, file_prefix
from google.cloud import storage

storage_client = storage.Client(project=GCP_PROJECT_ID)


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
