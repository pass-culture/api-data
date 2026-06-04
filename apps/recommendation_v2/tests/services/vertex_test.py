import pytest
from fastapi import HTTPException
from fastapi import status
from google.api_core import exceptions as gcp_exceptions

from services.vertex import VertexService


# ---------------------------------------------------------------------------
# VertexService.execute_grpc_prediction — auth error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_grpc_prediction_raises_http_401_on_auth_service_unavailable(mocker):
    """ServiceUnavailable containing an auth message is converted to HTTPException(401)."""

    service = VertexService(endpoint_name="test-endpoint")
    mock_client = mocker.AsyncMock()
    mock_client.predict.side_effect = gcp_exceptions.ServiceUnavailable("Reauthentication is needed. Run gcloud auth.")
    mocker.patch.object(
        service, "_get_cached_prediction_client", new_callable=mocker.AsyncMock, return_value=mock_client
    )
    mocker.patch.object(
        service,
        "_resolve_endpoint_resource_path",
        new_callable=mocker.AsyncMock,
        return_value="projects/123/locations/europe-west1/endpoints/456",
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.execute_grpc_prediction(feature_payloads=[{"user_id": "u"}])

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_execute_grpc_prediction_reraises_non_auth_service_unavailable(mocker):
    """A ServiceUnavailable that is not auth-related must propagate as-is so the caller can handle it."""
    service = VertexService(endpoint_name="test-endpoint")
    original_error = gcp_exceptions.ServiceUnavailable("upstream service down")
    mock_client = mocker.AsyncMock()
    mock_client.predict.side_effect = original_error
    mocker.patch.object(
        service, "_get_cached_prediction_client", new_callable=mocker.AsyncMock, return_value=mock_client
    )
    mocker.patch.object(
        service,
        "_resolve_endpoint_resource_path",
        new_callable=mocker.AsyncMock,
        return_value="projects/123/locations/europe-west1/endpoints/456",
    )

    with pytest.raises(gcp_exceptions.ServiceUnavailable) as exc_info:
        await service.execute_grpc_prediction(feature_payloads=[{"user_id": "u"}])

    assert exc_info.value is original_error
