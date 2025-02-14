"""Main constants of the project."""

import os
from datetime import datetime

ENV_SHORT_NAME = os.environ.get("ENV_SHORT_NAME", "dev")
DATA_BUCKET_NAME = f"data-bucket-{ENV_SHORT_NAME}"
yyyy = datetime.now().year
file_prefix = f"elementary_reports/{yyyy}"
