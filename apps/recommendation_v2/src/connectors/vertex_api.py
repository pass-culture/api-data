import traceback

from fastapi import HTTPException
from pydantic import BaseModel

from schemas.vertex_prediction_item import ItemOrigin
from schemas.vertex_prediction_item import RecommendableItem
from services.logger import logger
from services.vertex import VertexService


class VertexPredictionResult(BaseModel):
    """Encapsulates the parsed response from the Retrieval Vertex Model."""

    status: str
    predictions: list[RecommendableItem] = []
    model_version: str = "unknown"
    model_display_name: str = "unknown"


class RankingPrediction(BaseModel):
    """Encapsulates a single scored offer returned by the Ranking Vertex Model."""

    offer_id: str
    score: float


def get_item_origin(model_type: str) -> ItemOrigin:
    """Deduce item_origin from model_type.

    Args:
        model_type (str): The model type from the feature payload (e.g. 'recommendation', 'similar_offer', 'tops').

    Returns:
        ItemOrigin: The corresponding item_origin enum value.
    """
    model_type_to_item_origin: dict[str, ItemOrigin] = {
        "recommendation": ItemOrigin.USER_BASED,
        "similar_offer": ItemOrigin.USER_BASED,
        "tops": ItemOrigin.TOPS,
    }

    if model_type not in model_type_to_item_origin:
        logger.error(
            "Unknown model type",
            extra={"unknown_model_type": model_type, "allowed_model_types": model_type_to_item_origin.keys()},
        )
        raise ValueError(
            f"Unknown model_type '{model_type}'. Expected one of: {list(model_type_to_item_origin.keys())}"
        )

    return model_type_to_item_origin[model_type]


class VertexAPI:
    """
    Business-level API wrapper for Vertex AI models.

    This class acts as an adapter. It delegates the low-level network and
    gRPC communication to the `VertexService` and focuses strictly on validating
    and parsing the raw Protobuf responses into typed Pydantic business models.

    Architecture Context:
    -------------------
    +----------------+       +-------------------+       +--------------------+
    |   Core Logic   | ----> |     VertexAPI     | ----> |   VertexService    |
    | (retrieval.py) | <---- | (Pydantic Models) | <---- | (Raw gRPC/Protobuf)|
    +----------------+       +-------------------+       +--------------------+

    Example:
        vertex_api = VertexAPI(endpoint_name="my-endpoint")
        predictions = await vertex_api.fetch_ranking_predictions(feature_payloads=[...])
    """

    def __init__(self, endpoint_name: str, location: str = "europe-west1"):
        self.endpoint_name = endpoint_name
        self.vertex_infrastructure_service = VertexService(endpoint_name=endpoint_name, location=location)

    async def fetch_retrieval_predictions(self, feature_payloads: list[dict]) -> VertexPredictionResult:
        """
        Calls the Retrieval model to get a massive list of candidate items.
        This endpoint returns a rich dictionary for each predicted item, which is
        parsed into strictly typed Pydantic models (RecommendableItem) for downstream safety.

        Args:
            feature_payloads (list[dict]): The search context and user constraints.

        Returns:
            VertexPredictionResult: The standardized wrapper containing the list of items.
        """
        try:
            # --- 1. Execute Network Call via Infrastructure Service ---
            response = await self.vertex_infrastructure_service.execute_grpc_prediction(feature_payloads)

            # --- 2. Parse Protobuf Response into Pydantic Models ---
            model_type = feature_payloads[0]["model_type"]
            item_origin = get_item_origin(model_type)

            parsed_predictions = []
            for raw_prediction in response.predictions:
                parsed_item = RecommendableItem(
                    item_id=raw_prediction["item_id"],
                    item_rank=raw_prediction["idx"],
                    item_score=raw_prediction.get("_distance", None),
                    item_origin=item_origin,
                    item_cluster_id=raw_prediction.get("cluster_id", None),
                    item_topic_id=raw_prediction.get("topic_id", None),
                    semantic_emb_mean=raw_prediction.get("semantic_emb_mean", None),
                    is_geolocated=bool(raw_prediction["is_geolocated"]),
                    booking_number=raw_prediction["booking_number"],
                    booking_number_last_7_days=raw_prediction["booking_number_last_7_days"],
                    booking_number_last_14_days=raw_prediction["booking_number_last_14_days"],
                    booking_number_last_28_days=raw_prediction["booking_number_last_28_days"],
                    stock_price=raw_prediction["stock_price"],
                    category=raw_prediction["category"],
                    subcategory_id=raw_prediction["subcategory_id"],
                    search_group_name=raw_prediction["search_group_name"],
                    offer_creation_date=raw_prediction["offer_creation_date"],
                    stock_beginning_date=raw_prediction["stock_beginning_date"],
                    gtl_id=raw_prediction["gtl_id"],
                    gtl_l3=raw_prediction["gtl_l3"],
                    gtl_l4=raw_prediction["gtl_l4"],
                    total_offers=raw_prediction["total_offers"],
                    example_offer_id=raw_prediction.get("example_offer_id", None),
                    example_venue_latitude=raw_prediction.get("example_venue_latitude", None),
                    example_venue_longitude=raw_prediction.get("example_venue_longitude", None),
                )
                parsed_predictions.append(parsed_item)

            return VertexPredictionResult(
                status="success",
                model_version=response.deployed_model_id,
                predictions=parsed_predictions,
            )

        except HTTPException:
            raise

        except Exception as error:
            logger.error(
                f"💥 Vertex Retrieval Prediction failed for {self.endpoint_name}",
                extra={"error": str(error), "traceback": traceback.format_exc()},
            )
            # Fail gracefully by returning an empty list rather than crashing the API
            return VertexPredictionResult(status="error", model_display_name=self.endpoint_name, predictions=[])

    async def fetch_ranking_predictions(self, feature_payloads: list[dict]) -> list[RankingPrediction]:
        """
        Calls the Ranking model to score a specific list of resolved offers.

        Args:
            feature_payloads (list[dict]): The enriched features for the user and each offer.

        Returns:
            list[RankingPrediction]: The validated offer IDs mapped to their ML score.
        """
        try:
            # --- 1. Execute Network Call via Infrastructure Service ---
            response = await self.vertex_infrastructure_service.execute_grpc_prediction(feature_payloads)

            # --- 2. Parse & Validate Protobuf Response ---
            parsed_results = []
            for raw_prediction in response.predictions:
                try:
                    ranked_item = RankingPrediction(
                        offer_id=str(raw_prediction["offer_id"]), score=float(raw_prediction["score"])
                    )
                    parsed_results.append(ranked_item)

                except (KeyError, ValueError) as format_error:
                    logger.warning(
                        f"⚠️ Invalid ranking prediction format received: {raw_prediction}",
                        extra={"error": str(format_error)},
                    )
                    continue

            return parsed_results

        except HTTPException:
            raise

        except Exception as error:
            logger.error(
                f"💥 Vertex Ranking Prediction failed for {self.endpoint_name}",
                extra={"error": str(error), "traceback": traceback.format_exc()},
            )
            # Fail gracefully, the caller will fallback to standard ranking
            return []
