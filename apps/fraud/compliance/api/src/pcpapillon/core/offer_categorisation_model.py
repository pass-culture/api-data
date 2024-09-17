import pandas as pd
from main import custom_logger
from pcpapillon.utils.constants import (
    ModelName,
)
from pcpapillon.utils.data_model import (
    OfferCategorisationInput,
    OfferCategorisationOutput,
)
from pcpapillon.utils.model_handler import ModelHandler, ModelWithMetadata


class OfferCategorisationModel:
    MODEL_NAME = ModelName.OFFER_CATEGORISATION
    NUM_OFFERS_TO_RETURN = 3

    def __init__(self):
        self.model_handler = ModelHandler()
        model_data = self._load_models()
        self.model = model_data.model

    def predict(self, data: OfferCategorisationInput) -> OfferCategorisationOutput:
        """
        Predicts the class labels for the given data using the trained classifier model.

        Args:
            data (ComplianceInput): Input data to be predicted.

        Returns:
            ComplianceOutput: An object containing the predicted class labels
                and the main contributions.
        """
        predictions = self.model.predict(data.dict())
        predictions_df = (
            pd.DataFrame(
                {
                    "subcategory": predictions.subcategory,
                    "probability": predictions.probability,
                }
            )
            .sort_values("probability", ascending=False)
            .iloc[: self.NUM_OFFERS_TO_RETURN]
        )

        return OfferCategorisationOutput(
            most_probable_subcategories=predictions_df.to_dict(orient="records")
        )

    def _load_models(self) -> ModelWithMetadata:
        custom_logger.info("Load offer categorisation model..")
        return self.model_handler.get_model_with_metadata_by_name(
            model_name=self.MODEL_NAME
        )
