import time

import pandas as pd
from catboost import CatBoostClassifier
from fastapi import APIRouter, Depends
from fastapi_versioning import version
from main import custom_logger, setup_trace
from pcpapillon.utils.data_model import (
    OfferCategorisationInput,
    OfferCategorisationOutput,
)
from sentence_transformers import SentenceTransformer

offer_categorisation_router = APIRouter(tags=["offer_categorisation"])


# Add auto_class_weights to balance
instantiated_text_encoder = SentenceTransformer(
    "sentence-transformers/all-MiniLM-L6-v2"
)
instantiated_model_classifier = CatBoostClassifier(
    one_hot_max_size=65, loss_function="MultiClass", auto_class_weights="Balanced"
)
instantiated_model_classifier.load_model(
    "pcpapillon/local_model/offer_categorisation_model.cb"
)
label_mapping = pd.read_parquet(
    "pcpapillon/data/offer_categorisation_label_mapping.parquet"
)
classes_to_label_mapping = label_mapping.iloc[instantiated_model_classifier.classes_][
    "offer_subcategoryId"
]


def preprocess(input: OfferCategorisationInput, sementinc_encoder: SentenceTransformer):
    t0 = time.time()

    input_series = pd.Series(input.dict()).fillna("unkn")
    content = [
        "offer_name",
        "offer_description",
        "offer_type_label",
        "offer_sub_type_label",
        "author",
        "performer",
    ]
    sementic_content = " ".join(input_series[content].astype(str))
    custom_logger.info(f"sementic_content: {sementic_content}")

    output_series = pd.Series(
        {
            "venue_type_label": input.venue_type_label,
            "offerer_name": input.offerer_name,
            "embedding": sementinc_encoder.encode(sementic_content),
        }
    )

    custom_logger.info(f"elapsed_time for preprocessing with LLM {time.time() - t0}")
    return output_series


def predict(preprocessed_input: pd.Series, model_classifier: CatBoostClassifier):
    t0 = time.time()
    probabilities = model_classifier.predict_proba(preprocessed_input)
    custom_logger.info(f"elapsed_time for Catboost {time.time() - t0}")

    return probabilities


def postprocess(
    probabilities: pd.Series,
    classes_to_label_mapping: pd.Series,
    n_top: int,
):
    t0 = time.time()

    top_indexes = probabilities.argsort()[-n_top:][::-1]
    top_categories = classes_to_label_mapping.iloc[top_indexes]

    custom_logger.info(f"elapsed_time for postprocessing {time.time() - t0}")

    return pd.DataFrame(
        {
            "category": top_categories,
            "probability": probabilities[top_indexes],
        }
    ).to_dict(orient="records")


@offer_categorisation_router.post(
    "/model/offer_categorisation/scoring",
    response_model=OfferCategorisationOutput,
    dependencies=[Depends(setup_trace)],
)
@version(1, 0)
def model_compliance_scoring(input: OfferCategorisationInput):
    log_extra_data = {
        "model_version": "default_model",
        "offer_id": input.dict()["offer_id"],
        "scoring_input": input.dict(),
    }

    preprocessed_input = preprocess(
        input=input, sementinc_encoder=instantiated_text_encoder
    )

    probabilities = predict(
        preprocessed_input=preprocessed_input,
        model_classifier=instantiated_model_classifier,
    )

    most_probable_categories = postprocess(
        probabilities=probabilities,
        classes_to_label_mapping=classes_to_label_mapping,
        n_top=3,
    )

    output_data = {
        "offer_id": input.offer_id,
        "most_probable_categories": most_probable_categories,
    }
    custom_logger.info(output_data, extra=log_extra_data)
    return output_data
