import time

import numpy as np
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
    LABEL_MAPPING_PATH = "pcpapillon/data/offer_categorisation_label_mapping.parquet"  # Will be removed when model predict is updated
    MODEL_NAME = ModelName.OFFER_CATEGORISATION

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
        print(predictions)
        return predictions
        # return OfferCategorisationOutput(
        #     **pd.DataFrame(
        #         {
        #             "subcategory": top_categories,
        #             "probability": probabilities[top_indexes],
        #         }
        #     ).to_dict(orient="records")
        # )

    def _postprocess(
        self,
        probabilities: pd.Series,
        n_top: int,
    ):
        t0 = time.time()

        top_indexes = probabilities.argsort()[-n_top:][::-1]
        top_categories = self.classes_to_label_mapping.iloc[top_indexes]

        custom_logger.debug(f"elapsed time for postprocessing {time.time() - t0}")

        return pd.DataFrame(
            {
                "subcategory": top_categories,
                "probability": probabilities[top_indexes],
            }
        ).to_dict(orient="records")

    def _load_models(self) -> ModelWithMetadata:
        custom_logger.info("Load offer categorisation model..")
        return self.model_handler.get_model_with_metadata_by_name(
            model_name=self.MODEL_NAME
        )

    @classmethod
    def _load_classes_to_label_mapping(cls, model_classes: np.ndarray) -> pd.Series:
        label_mapping = pd.read_parquet(cls.LABEL_MAPPING_PATH)
        return label_mapping.iloc[model_classes]["offer_subcategoryId"]
