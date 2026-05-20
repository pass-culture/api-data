import re
from datetime import UTC
from datetime import datetime

import pytest

import config.settings as _settings
from core.tracking import log_past_offer_context_to_sink
from models.past_offer_context import PastOfferContext
from schemas.playlist_recommendation import PlaylistRequestParams
from schemas.tracking_payload import TrackingLabels
from schemas.tracking_payload import TrackingLogPayload
from schemas.tracking_payload import TrackingOfferExtraData
from schemas.tracking_payload import TrackingRequestExtraData

from tests.factories.schemas import EnrichedRecommendableOfferFactory
from tests.factories.schemas import UserContextFactory


_SNAKE_CASE = re.compile(r"^[a-z][a-z0-9_]*$")

# Fields in TrackingLogPayload with no PastOfferContext column (GCP/API metadata only)
_TRACKING_ONLY_FIELDS = {"labels", "recommendation_api_version"}

# Test date parametrization
CREATION_DATE = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
STOCK_DATE = datetime(2024, 6, 1, 0, 0, 0, tzinfo=UTC)

@pytest.fixture(autouse=True)
def _tracking_enabled(mocker):
    """Force tracking on regardless of the local .env so logger.info is always reachable."""
    mocker.patch.object(_settings, "ENABLE_TRACKING_LOGS", new=True)


def _invoke(offers, params=None, call_id="call-abc"):
    log_past_offer_context_to_sink(
        user_context=UserContextFactory.build(),
        final_playlist=offers,
        params=params,
        call_id=call_id,
        reco_origin="algo",
        context_name="playlist",
    )


def test_tracking_payload_all_field_names_are_snake_case():
    """All field names must be snake_case — other conventions break the BigQuery sink routing."""
    models = [TrackingLogPayload, TrackingLabels, TrackingRequestExtraData, TrackingOfferExtraData]
    violations = [
        f"{model.__name__}.{field}" for model in models for field in model.model_fields if not _SNAKE_CASE.match(field)
    ]
    assert not violations, f"Non-snake_case field names: {violations}"


def test_tracking_payload_schema_matches_db():
    """
    Assert 1:1 mapping between PastOfferContext DB columns and TrackingLogPayload fields.

    Catches schema drift statically. Fails if a database migration introduces a
    column that isn't mirrored in the Pydantic model, or vice-versa.
    """
    orm_columns = {col.key for col in PastOfferContext.__table__.columns} - {"id"}
    pydantic_fields = set(TrackingLogPayload.model_fields) - _TRACKING_ONLY_FIELDS

    missing = orm_columns - pydantic_fields
    assert not missing, f"TrackingLogPayload is missing PastOfferContext columns: {missing}"

    extra = pydantic_fields - orm_columns
    assert not extra, f"TrackingLogPayload has fields with no PastOfferContext column: {extra}"


def test_tracking_emits_valid_payload_format(mocker):
    """
    Verify that the application logic outputs a payload matching the Pydantic schema.

    Runs the pipeline and validates the logger's `extra` arguments. Fails with a
    ValidationError if fields are missing, misspelled, or have incorrect types at runtime.
    """
    mock_logger = mocker.patch("core.tracking.logger.info")

    _invoke([EnrichedRecommendableOfferFactory.build()])

    TrackingLogPayload.model_validate(mock_logger.call_args.kwargs["extra"])


def test_tracking_payload_has_no_unexpected_top_level_keys(mocker):
    """New keys added silently would break the BigQuery table schema."""
    mock_logger = mocker.patch("core.tracking.logger.info")

    _invoke([EnrichedRecommendableOfferFactory.build()])

    extra_keys = mock_logger.call_args.kwargs["extra"].keys() - set(TrackingLogPayload.model_fields)
    assert not extra_keys, f"Unexpected keys in payload: {extra_keys}"


def test_tracking_offer_extra_data_contains_all_required_keys(mocker):
    """offer_extra_data is a nested BigQuery RECORD — its keys are equally load-bearing."""
    mock_logger = mocker.patch("core.tracking.logger.info")

    _invoke([EnrichedRecommendableOfferFactory.build()])

    TrackingOfferExtraData.model_validate(mock_logger.call_args.kwargs["extra"]["offer_extra_data"])


def test_tracking_payload_gcp_sink_label_routes_to_correct_bigquery_table(mocker):
    """A rename of labels.event_type silently stops all data from reaching BigQuery."""
    mock_logger = mocker.patch("core.tracking.logger.info")

    _invoke([EnrichedRecommendableOfferFactory.build()])

    assert mock_logger.call_args.kwargs["extra"]["labels"]["event_type"] == "recommendation_past_offer_context_sink"


def test_tracking_payload_top_level_date_is_iso_string(mocker):
    """BigQuery DATETIME ingestion requires ISO-8601 strings — a raw datetime object breaks the sink."""
    mock_logger = mocker.patch("core.tracking.logger.info")

    _invoke([EnrichedRecommendableOfferFactory.build()])

    date_value = mock_logger.call_args.kwargs["extra"]["date"]
    assert isinstance(date_value, str), f"Expected str, got {type(date_value)}"
    datetime.fromisoformat(date_value)


@pytest.mark.parametrize(
    ("factory_field", "log_key", "datetime_value"),
    [
        ("offer_creation_date", "offer_creation_date", CREATION_DATE),
        ("stock_beginning_date", "offer_stock_beginning_date", STOCK_DATE),
    ],
)
def test_tracking_payload_datetime_fields_are_iso_strings_when_set(
    mocker, factory_field, log_key, datetime_value
):
    """Verify datetime fields are correctly serialized to ISO format strings in the log payload."""
    mock_logger = mocker.patch("core.tracking.logger.info")

    # On construit dynamiquement l'argument de la factory
    factory_kwargs = {factory_field: datetime_value}
    _invoke([EnrichedRecommendableOfferFactory.build(**factory_kwargs)])

    value = mock_logger.call_args.kwargs["extra"][log_key]

    assert isinstance(value, str)
    assert datetime.fromisoformat(value) == datetime_value


@pytest.mark.parametrize(
    ("factory_field", "log_key"),
    [
        ("offer_creation_date", "offer_creation_date"),
        ("stock_beginning_date", "offer_stock_beginning_date"),
    ],
)
def test_tracking_payload_datetime_fields_are_none_when_not_set(
    mocker, factory_field, log_key
):
    """Verify datetime fields remain None in the log payload when they are not provided."""
    mock_logger = mocker.patch("core.tracking.logger.info")

    factory_kwargs = {factory_field: None}
    _invoke([EnrichedRecommendableOfferFactory.build(**factory_kwargs)])

    assert mock_logger.call_args.kwargs["extra"][log_key] is None


def test_tracking_payload_offer_order_matches_list_index(mocker):
    """offer_order drives ranking performance analysis — must equal the 0-based playlist position."""
    mock_logger = mocker.patch("core.tracking.logger.info")
    batch_size = 3

    _invoke(EnrichedRecommendableOfferFactory.batch(batch_size))

    assert mock_logger.call_count == batch_size
    for expected_index, call in enumerate(mock_logger.call_args_list):
        assert call.kwargs["extra"]["offer_order"] == expected_index


def test_tracking_ranking_origin_is_model_when_ranking_score_is_nonzero(mocker):
    """ranking_origin='model' tells Data Scientists the Vertex score is the training signal."""
    mock_logger = mocker.patch("core.tracking.logger.info")

    ranking_score = 0.87
    _invoke([EnrichedRecommendableOfferFactory.build(ranking_score=ranking_score)])

    extra = mock_logger.call_args.kwargs["extra"]["offer_extra_data"]
    assert extra["offer_ranking_origin"] == "model"
    assert extra["offer_ranking_score"] == ranking_score


def test_tracking_ranking_origin_is_item_rank_when_ranking_score_is_zero(mocker):
    """ranking_score=0.0 means Vertex was skipped — fallback item_rank sort was used."""
    mock_logger = mocker.patch("core.tracking.logger.info")

    _invoke([EnrichedRecommendableOfferFactory.build(ranking_score=0.0)])

    assert mock_logger.call_args.kwargs["extra"]["offer_extra_data"]["offer_ranking_origin"] == "item_rank"


def test_tracking_logs_nothing_for_empty_playlist(mocker):
    mock_logger = mocker.patch("core.tracking.logger.info")

    _invoke([])

    mock_logger.assert_not_called()


def test_tracking_params_in_is_none_when_params_is_none(mocker):
    mock_logger = mocker.patch("core.tracking.logger.info")

    _invoke([EnrichedRecommendableOfferFactory.build()], params=None)

    assert mock_logger.call_args.kwargs["extra"]["context_extra_data"]["params_in"] is None


def test_tracking_params_in_is_serialized_dict_when_params_provided(mocker):
    mock_logger = mocker.patch("core.tracking.logger.info")

    price_max = 50.0
    _invoke([EnrichedRecommendableOfferFactory.build()], params=PlaylistRequestParams(price_max=price_max, is_duo=True))

    params_in = mock_logger.call_args.kwargs["extra"]["context_extra_data"]["params_in"]
    assert isinstance(params_in, dict)
    assert params_in["priceMax"] == price_max
    assert params_in["isDuo"] is True


def test_tracking_suppresses_log_when_enable_tracking_logs_is_false(mocker):
    """IS_LOCAL + ENABLE_TRACKING_LOGS=False is the local dev noise-suppression flag."""
    mocker.patch.object(_settings, "ENABLE_TRACKING_LOGS", new=False)
    mock_logger = mocker.patch("core.tracking.logger.info")

    _invoke([EnrichedRecommendableOfferFactory.build()])

    mock_logger.assert_not_called()
