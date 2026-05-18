"""Main constants of the project."""

import os
from datetime import datetime

ENV_SHORT_NAME = os.environ.get(
    "ENV_SHORT_NAME", "stg"
)  # No reports in dev, so default to staging environment
GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "passculture-data-ehp")
DATA_BUCKET_NAME = f"de-bigquery-data-export-{ENV_SHORT_NAME}"
ELEMENTARY_REPORTS_PREFIX = f"elementary_reports/{datetime.now().year}"
