import time

import numpy as np
import pandas as pd
from catboost import CatBoostClassifier
from main import custom_logger
from pcpapillon.utils.constants import (
    ModelName,
    ModelType,
)
from pcpapillon.utils.data_model import (
    OfferCategorisationInput,
)
from pcpapillon.utils.env_vars import (
    IS_API_LOCAL,
)
from pcpapillon.utils.model_handler import ModelHandler
from sentence_transformers import SentenceTransformer


class OfferCategorisationModel:
    LABEL_MAPPING_PATH = "pcpapillon/data/offer_categorisation_label_mapping.parquet"  # Will be removed when model predict is updated
    PREPROCESSOR_NAME = "sentence-transformers/all-MiniLM-L6-v2"  # Will be removed when model predict is updated
    MODEL_NAME = ModelName.OFFER_CATEGORISATION
    MODEL_TYPE = ModelType.LOCAL if IS_API_LOCAL else ModelType.DEFAULT
    PREPROC_MODEL_TYPE = ModelType.PREPROCESSING

    def __init__(self):
        self.model_handler = ModelHandler()
        self.model_classifier, self.sementinc_encoder = self._load_models()
        self.classes_to_label_mapping = self._load_classes_to_label_mapping(
            self.model_classifier.classes_
        )

    def predict(
        self, input: OfferCategorisationInput, num_offers_to_return: int
    ) -> pd.Series:
        preprocessed_input = self._preprocess(input=input)

        probabilities = self._classify(
            preprocessed_input=preprocessed_input,
        )

        return self._postprocess(
            probabilities=probabilities,
            n_top=num_offers_to_return,
        )

    def _preprocess(self, input: OfferCategorisationInput):
        t0 = time.time()

        input_series = pd.Series(input.dict()).fillna("unkn")
        content = [
            "offer_name",
            "offer_description",
        ]
        sementic_content = " ".join(input_series[content].astype(str))
        custom_logger.debug(f"sementic_content: {sementic_content}")

        output_series = pd.Series(
            {
                "venue_type_label": input.venue_type_label,
                "offerer_name": input.offerer_name,
                "embedding": self.sementinc_encoder.encode(sementic_content),
            }
        )

        custom_logger.debug(
            f"elapsed time for preprocessing the input (LLM embedding extraction) {time.time() - t0}"
        )
        return output_series

    def _classify(
        self,
        preprocessed_input: pd.Series,
    ):
        t0 = time.time()
        probabilities = self.model_classifier.predict_proba(preprocessed_input)
        custom_logger.debug(
            f"elapsed time for classification (CatBoost) {time.time() - t0}"
        )

        return probabilities

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

    def _load_models(self) -> tuple[CatBoostClassifier, SentenceTransformer]:
        custom_logger.info("Load offer categorisation model..")
        model_classifier = self.model_handler.get_model_with_metadata_by_name(
            model_name=self.MODEL_NAME, model_type=self.MODEL_TYPE
        ).model

        custom_logger.info("Load offer categorisation model preprocessor..")
        text_preprocessor = self.model_handler.get_model_with_metadata_by_name(
            model_name=self.PREPROCESSOR_NAME,
            model_type=self.PREPROC_MODEL_TYPE,
        ).model

        return model_classifier, text_preprocessor

    @classmethod
    def _load_classes_to_label_mapping(cls, model_classes: np.ndarray) -> pd.Series:
        label_mapping = pd.read_parquet(cls.LABEL_MAPPING_PATH)
        return label_mapping.iloc[model_classes]["offer_subcategoryId"]
