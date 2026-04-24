import uuid
from datetime import UTC
from datetime import datetime
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

from config import settings
from connectors.vertex_api import VertexPredictionResult
from main import app
from schemas.vertex_prediction_item import RecommendableItem
from services.db import get_database_session


MOCK_CALL_ID = "12345678-1234-5678-1234-567812345678"

# Force Redis cache to be disabled during tests
settings.REDIS_CACHE_ENABLED = False


@pytest.fixture(scope="session", autouse=True)
def mock_uuid():
    """
    Global mock for UUID generation.
    Ensures that all generated call_ids are identical and predictable.
    """
    with patch("core.pipeline.uuid.uuid4") as mock_uuid_func:
        mock_uuid_func.return_value = uuid.UUID(MOCK_CALL_ID)
        yield mock_uuid_func


@pytest.fixture(scope="session", autouse=True)
def mock_vertex_services():
    """
    Global mock for Vertex AI application services calls.
    Allows bypassing real model calls without altering the local pipeline.
    """
    with (
        patch("core.pipeline.fetch_candidate_items_from_vertex", new_callable=AsyncMock) as mock_fetch,
        patch("core.pipeline.rank_and_sort_offers_with_vertex", new_callable=AsyncMock) as mock_rank,
    ):

        def _create_recommendable_item(item_id: str) -> RecommendableItem:
            return RecommendableItem(
                item_id=item_id,
                item_origin="algo",
                item_rank=1,
                item_score=1.0,
                item_cluster_id=None,
                item_topic_id=None,
                semantic_emb_mean=1.0,
                booking_number=0,
                booking_number_last_7_days=0,
                booking_number_last_14_days=0,
                booking_number_last_28_days=0,
                stock_price=10.0,
                category="test",
                subcategory_id="test",
                search_group_name="test",
                offer_creation_date=datetime.now(UTC),
                stock_beginning_date=datetime.now(UTC),
                gtl_id=None,
                gtl_l3=None,
                gtl_l4=None,
                is_geolocated=False,
                total_offers=1,
                example_offer_id=item_id,
                example_venue_latitude=None,
                example_venue_longitude=None,
            )

        # Simulating the retrieval of recommendation candidates
        mock_fetch.return_value = VertexPredictionResult(
            status="success",
            predictions=[
                _create_recommendable_item("1"),
                _create_recommendable_item("2"),
                _create_recommendable_item("3"),
            ],
        )

        # Simulating the scoring/ranking model
        async def fake_ranking_func(offers, user_context):
            return offers

        mock_rank.side_effect = fake_ranking_func

        yield {"mock_fetch": mock_fetch, "mock_rank": mock_rank}


@pytest.fixture(scope="module")
def client():
    async def override_get_database_session():
        mock_session = AsyncMock()

        # Simulate the absence of a known user
        mock_session.get.return_value = None

        # Simulate an absence of already booked offers for the user
        # We use MagicMock for the result because .scalars().all() is synchronous on the result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        yield mock_session

    app.dependency_overrides[get_database_session] = override_get_database_session

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
