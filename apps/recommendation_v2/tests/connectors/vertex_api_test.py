from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from fastapi import status

from schemas.vertex_prediction_item import ItemOrigin


def _grpc_response(predictions: list, deployed_model_id: str = "model-v1") -> MagicMock:
    response = MagicMock()
    response.predictions = predictions
    response.deployed_model_id = deployed_model_id
    return response


def _make_raw_retrieval_prediction(**overrides) -> dict:
    """Raw gRPC dict — field names differ from RecommendableItem (e.g. ``idx`` vs ``item_rank``)."""
    base = {
        "item_id": "item-1",
        "idx": 0,
        "_distance": 0.5,
        "cluster_id": "cluster-1",
        "topic_id": "topic-1",
        "semantic_emb_mean": 0.3,
        "is_geolocated": 1,
        "booking_number": 10,
        "booking_number_last_7_days": 2,
        "booking_number_last_14_days": 4,
        "booking_number_last_28_days": 7,
        "stock_price": 9.99,
        "category": "LIVRE",
        "subcategory_id": "LIVRE_PAPIER",
        "search_group_name": "LIVRES",
        "offer_creation_date": "2024-01-01T00:00:00",
        "stock_beginning_date": "2024-06-01T00:00:00",
        "gtl_id": "gtl-1",
        "gtl_l3": "Fiction",
        "gtl_l4": "Science Fiction",
        "total_offers": 5,
        "example_offer_id": "offer-1",
        "example_venue_latitude": 48.8566,
        "example_venue_longitude": 2.3522,
    }
    return {**base, **overrides}


# ---------------------------------------------------------------------------
# fetch_retrieval_predictions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("feature_payloads", "expected_item_origin"),
    [
        ([{"model_type": "recommendation"}], ItemOrigin.USER_BASED),
        ([{"model_type": "similar_offer"}], ItemOrigin.USER_BASED),
        ([{"model_type": "tops"}], ItemOrigin.TOPS),
    ],
)
async def test_fetch_retrieval_maps_renamed_grpc_fields(vertex_api, feature_payloads, expected_item_origin):
    """
    gRPC key names differ from Pydantic field names
    this pins the mapping so a rename in either schema won't go unnoticed.
    """
    rank = 3
    dist = 0.75
    raw = _make_raw_retrieval_prediction(idx=rank, _distance=dist, cluster_id="clu-1", topic_id="top-1")
    vertex_api.vertex_infrastructure_service.execute_grpc_prediction.return_value = _grpc_response([raw])

    item = (await vertex_api.fetch_retrieval_predictions(feature_payloads=feature_payloads)).predictions[0]

    assert item.item_rank == rank  # idx → item_rank
    assert item.item_score == dist  # _distance → item_score
    assert item.item_cluster_id == "clu-1"  # cluster_id → item_cluster_id
    assert item.item_topic_id == "top-1"  # topic_id → item_topic_id
    assert item.item_origin == expected_item_origin


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("feature_payloads", "expected_item_origin"),
    [
        ([{"model_type": "similar_offer"}], ItemOrigin.GRAPH),
        ([{"model_type": "tops"}], ItemOrigin.TOPS),  # tops fallback overrides graph
    ],
)
async def test_fetch_retrieval_graph_endpoint_sets_item_origin(
    graph_vertex_api, feature_payloads, expected_item_origin
):
    """
    When the graph endpoint is used, item_origin must be GRAPH — unless the model fell back
    to 'tops', in which case item_origin stays TOPS regardless of the endpoint.
    """
    raw = _make_raw_retrieval_prediction()
    graph_vertex_api.vertex_infrastructure_service.execute_grpc_prediction.return_value = _grpc_response([raw])

    item = (await graph_vertex_api.fetch_retrieval_predictions(feature_payloads=feature_payloads)).predictions[0]

    assert item.item_origin == expected_item_origin


@pytest.mark.asyncio
async def test_fetch_retrieval_casts_is_geolocated_int_to_bool(vertex_api):
    """gRPC returns is_geolocated as an integer; the connector explicitly casts it via bool()."""
    vertex_api.vertex_infrastructure_service.execute_grpc_prediction.return_value = _grpc_response(
        [
            _make_raw_retrieval_prediction(item_id="a", is_geolocated=1),
            _make_raw_retrieval_prediction(item_id="b", is_geolocated=0),
        ]
    )

    predictions = (
        await vertex_api.fetch_retrieval_predictions(feature_payloads=[{"model_type": "recommendation"}])
    ).predictions

    assert predictions[0].is_geolocated is True
    assert predictions[1].is_geolocated is False


@pytest.mark.asyncio
async def test_fetch_retrieval_reraises_http_exception(vertex_api):
    vertex_api.vertex_infrastructure_service.execute_grpc_prediction.side_effect = HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE
    )

    with pytest.raises(HTTPException) as exc_info:
        await vertex_api.fetch_retrieval_predictions(feature_payloads=[{}])

    assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


@pytest.mark.asyncio
async def test_fetch_retrieval_returns_error_result_on_unexpected_exception(vertex_api):
    """Any non-HTTP error is swallowed and returned as a typed error result so the endpoint stays alive.

    The caller can inspect status=="error" and model_display_name to identify which endpoint failed.
    """
    vertex_api.vertex_infrastructure_service.execute_grpc_prediction.side_effect = RuntimeError("network timeout")

    result = await vertex_api.fetch_retrieval_predictions(feature_payloads=[{}])

    assert result.status == "error"
    assert result.predictions == []
    assert result.model_display_name == "test-endpoint"


# ---------------------------------------------------------------------------
# fetch_ranking_predictions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_ranking_coerces_offer_id_to_string(vertex_api):
    """Vertex AI may return integer offer IDs; the connector wraps them in str() before building RankingPrediction."""
    vertex_api.vertex_infrastructure_service.execute_grpc_prediction.return_value = _grpc_response(
        [{"offer_id": 12345, "score": 0.7}]
    )

    result = await vertex_api.fetch_ranking_predictions(feature_payloads=[{}])

    assert result[0].offer_id == "12345"


@pytest.mark.asyncio
async def test_fetch_ranking_skips_malformed_prediction_and_keeps_valid_ones(vertex_api):
    """Per-item validation errors trigger a continue rather than aborting the whole list.

    A single bad prediction must not discard the valid ones that follow it.
    """
    raws = [{"offer_id": "offer-bad"}, {"offer_id": "offer-good", "score": 0.5}]
    vertex_api.vertex_infrastructure_service.execute_grpc_prediction.return_value = _grpc_response(raws)

    result = await vertex_api.fetch_ranking_predictions(feature_payloads=[{}])

    assert len(result) == 1
    assert result[0].offer_id == "offer-good"


@pytest.mark.asyncio
async def test_fetch_ranking_reraises_http_exception(vertex_api):
    vertex_api.vertex_infrastructure_service.execute_grpc_prediction.side_effect = HTTPException(
        status_code=status.HTTP_404_NOT_FOUND
    )

    with pytest.raises(HTTPException) as exc_info:
        await vertex_api.fetch_ranking_predictions(feature_payloads=[{}])

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_fetch_ranking_returns_empty_list_on_unexpected_exception(vertex_api):
    vertex_api.vertex_infrastructure_service.execute_grpc_prediction.side_effect = RuntimeError("grpc failure")

    result = await vertex_api.fetch_ranking_predictions(feature_payloads=[{}])

    assert result == []
