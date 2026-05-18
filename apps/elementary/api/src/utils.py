from datetime import datetime

from constants import DE_BUCKET_NAME, ELEMENTARY_REPORTS_PREFIX, GCP_PROJECT_ID
from google.cloud import storage

STORAGE_CLIENT = storage.Client(project=GCP_PROJECT_ID)
DE_BUCKET = STORAGE_CLIENT.bucket(DE_BUCKET_NAME)


def download_blob(source_blob_name: str) -> bytes:
    blob = DE_BUCKET.blob(source_blob_name)
    return blob.download_as_bytes()


def get_latest_file() -> str | None:
    latest_file = None
    latest_date = None

    for blob in DE_BUCKET.list_blobs(prefix=ELEMENTARY_REPORTS_PREFIX):
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
