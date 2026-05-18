from unittest.mock import patch

import pytest
from fastapi import Depends
from fastapi import FastAPI
from fastapi import status
from httpx import ASGITransport
from httpx import AsyncClient

from api.similar_artists import router as similar_artists_router
from config import settings
from main import verify_api_token
from services.db import get_database_session


VALID_ARTIST_ID = "0c1a0fe4-f2bf-4e1d-b9ac-7c46e4a6e2d6"
VALID_TOKEN = "valid-test-token"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("token_query_param", "expected_status_code"),
    [
        pytest.param(None, status.HTTP_401_UNAUTHORIZED, id="no_token_returns_401"),
        pytest.param("wrong-token", status.HTTP_401_UNAUTHORIZED, id="invalid_token_returns_401"),
        pytest.param(VALID_TOKEN, status.HTTP_200_OK, id="valid_token_returns_200"),
    ],
)
async def test_similar_artists_enforces_token_verification_when_not_local(
    db_session,
    token_query_param,
    expected_status_code,
):
    async def override_get_database_session():
        yield db_session

    test_app = FastAPI()
    test_app.include_router(
        similar_artists_router,
        dependencies=[Depends(verify_api_token)],
    )
    test_app.dependency_overrides[get_database_session] = override_get_database_session

    query_params = {"token": token_query_param} if token_query_param is not None else {}

    with patch.object(settings, "API_TOKEN", VALID_TOKEN):
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.get(
                f"/similar_artists/{VALID_ARTIST_ID}",
                params=query_params,
            )

    assert response.status_code == expected_status_code
