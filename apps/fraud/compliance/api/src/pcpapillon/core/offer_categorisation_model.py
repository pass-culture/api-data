import pandas as pd
from main import custom_logger
from pcpapillon.utils.constants import (
    ModelName,
)
from pcpapillon.utils.data_model import (
    CategoryOutput,
    OfferCategorisationInput,
)
from pcpapillon.utils.model_handler import ModelHandler, ModelWithMetadata


class OfferCategorisationModel:
    MODEL_NAME = ModelName.OFFER_CATEGORISATION

    def __init__(self):
        self.model_handler = ModelHandler()
        model_data = self._load_models()
        self.model = model_data.model
        self.model_identifier = model_data.model_identifier

    def predict(
        self, data: OfferCategorisationInput, num_offers_to_return: int
    ) -> list[CategoryOutput]:
        """
        Predicts the class labels for the given data using the trained classifier model.

        Args:
            data (ComplianceInput): Input data to be predicted.

        Returns:
            ComplianceOutput: An object containing the predicted class labels
                and the main contributions.
        """
        predictions = self.model.predict(data.dict())

        num_offers_to_return = min(num_offers_to_return, len(predictions.subcategory))
        predictions_df = (
            pd.DataFrame(
                {
                    "subcategory": predictions.subcategory,
                    "probability": predictions.probability,
                }
            )
            .sort_values("probability", ascending=False)
            .iloc[:num_offers_to_return]
        )

        custom_logger.info(
            "Offer categorisation done",
            extra={
                "predicted_subcategories": predictions_df.to_dict(orient="records"),
                "input_data": data.dict(),
                "model_version": self.model_identifier,
            },
        )
        return predictions_df.to_dict(orient="records")

    def _load_models(self) -> ModelWithMetadata:
        custom_logger.info("Load offer categorisation model..")
        return self.model_handler.get_model_with_metadata_by_name(
            model_name=self.MODEL_NAME
        )
