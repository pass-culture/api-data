import os

from google.cloud import bigquery


GCP_PROJECT = os.environ.get("GCP_PROJECT", "passculture-data-ehp")
ENV_SHORT_NAME = os.environ.get("ENV_SHORT_NAME", "stg")
DATASET_NAME = f"analytics_{ENV_SHORT_NAME}"
ARTIST_TABLE = f"{GCP_PROJECT}.{DATASET_NAME}.global_artist"


def fetch_artist_details(artist_id: str) -> dict | None:
    """
    Fetches artist metadata from BigQuery for a given artist_id.

    Returns:
    - dict with keys: artist_id, artist_name, artist_description, wikidata_image_file_url
      or None if not found.
    """
    client = bigquery.Client()
    query = f"""
        SELECT artist_id, artist_name, artist_description, wikidata_image_file_url
        FROM `{ARTIST_TABLE}`
        WHERE artist_id = @artist_id
        LIMIT 1
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("artist_id", "STRING", artist_id)]
    )
    results = client.query(query, job_config=job_config).result()
    rows = list(results)
    return dict(rows[0]) if rows else None


def fetch_artists_details_batch(artist_ids: list[str]) -> dict[str, dict]:
    """
    Fetches artist metadata from BigQuery for a list of artist_ids in a single query.

    Returns:
    - dict mapping artist_id → {artist_id, artist_name, artist_description, wikidata_image_file_url}
    """
    if not artist_ids:
        return {}

    client = bigquery.Client()
    query = f"""
        SELECT artist_id, artist_name, artist_description, wikidata_image_file_url
        FROM `{ARTIST_TABLE}`
        WHERE artist_id IN UNNEST(@artist_ids)
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ArrayQueryParameter("artist_ids", "STRING", artist_ids)]
    )
    results = client.query(query, job_config=job_config).result()
    return {row["artist_id"]: dict(row) for row in results}
