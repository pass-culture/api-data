import numpy as np
import pandas as pd
from catboost import CatBoostClassifier
from main import custom_logger
from pcpapillon.utils.env_vars import (
    isAPI_LOCAL,
)
from pcpapillon.utils.model_handler import ModelHandler
from sentence_transformers import SentenceTransformer


def load_models() -> tuple[CatBoostClassifier, SentenceTransformer]:
    custom_logger.info("Load offer categorisation model..")
    model_classifier = ModelHandler.get_model_by_name(
        name="offer_categorisation", type="local" if isAPI_LOCAL else "default"
    )

    custom_logger.info("Load offer categorisation model preprocessor..")
    text_preprocessor = ModelHandler.get_model_by_name(
        name="sentence-transformers/all-MiniLM-L6-v2",
        type="custom_sentence_transformer",
    )

    return model_classifier, text_preprocessor


def load_classes_to_label_mapping(model_classes: np.ndarray) -> pd.Series:
    label_mapping = pd.read_parquet(
        "pcpapillon/data/offer_categorisation_label_mapping.parquet"
    )
    return label_mapping.iloc[model_classes]["offer_subcategoryId"]
