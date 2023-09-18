import pytest
import numpy as np

# from catboost import Pool
from unittest.mock import Mock, patch, MagicMock, call
from pcpapillon.utils.configs import configs
from pcpapillon.core.preprocess import convert_data_to_catboost_pool
from pcpapillon.core.predict import (
    _get_contribution_from_shap_values,
    get_prediction_and_main_contribution,
)
from tests.conftest import model_config_default, model_handler_default


class PredictTest:
    @pytest.mark.parametrize(
        ["input_body", "expected_output"],
        [
            (
                {
                    "adipiscing": 6,
                    "aliqua": 18,
                    "magna": 17,
                    "et": 15,
                    "incididunt": 12,
                    "consectetur": 5,
                    "ut": 13,
                    "Lorem": 0,
                    "ipsum": 1,
                    "amet": 4,
                    "sed": 8,
                    "elit": 7,
                    "labore": 14,
                    "dolor": 2,
                    "eiusmod": 10,
                    "tempor": 11,
                    "sit": 3,
                    "dolore": 16,
                    "do": 9,
                },
                (["aliqua", "magna", "dolore"], ["Lorem", "ipsum", "dolor"]),
            )
        ],
    )
    def test_get_contribution_from_shap_values(self, input_body, expected_output):
        shap_values = list(input_body.values())
        n = len(shap_values)
        assert (
            tuple(
                _get_contribution_from_shap_values(
                    np.array(shap_values).reshape((1, n)), input_body
                )
            )
            == expected_output
        )

    #     @pytest.mark.parametrize(
    #         ["input_body", "expected_topval_toprej"],
    #         [
    #             (
    #                 {
    #                     "offer_name": "ninho 4 albums studio + poster",
    #                     "offer_description": "ninho 4 albums studio + poster",
    #                     "offer_subcategoryid": "SUPPORT_PHYSIQUE_MUSIQUE",
    #                     "rayon": "",
    #                     "macro_rayon": "",
    #                     "stock_price": 20,
    #                     "image_url": "https://storage.googleapis.com/passculture-metier-prod-production-assets-fine-grained/thumbs/products/9YKMS",
    #                     "offer_type_label": "rap conscient",
    #                     "offer_sub_type_label": "17",
    #                     "author": "ninho",
    #                     "performer": "judd Law",
    #                     "semantic_content": "ninho 4 albums studio + poster ninho 4 albums studio + poster rap conscient 17 ninho judd law"
    #                 },
    #                 {
    #                     "offer_id": "str",
    #                     "probability_validated": "int",
    #                     "validation_main_features": ["gratuit", "musée"],
    #                     "probability_rejected": "int",
    #                     "rejection_main_features": ["pas cool", "bon d"achat"],
    #                 },
    #                 #
    #             )])
    #     # @pytest.mark.parametrize(
    #             #  "data","expected_output",
    #             #  [
    #                 #  (
    #                     #  {"adipiscing": 6, "aliqua": 18, "magna": 17, "et": 15, "incididunt": 12, "consectetur": 5, "ut": 13, "Lorem": 0, "ipsum": 1, "amet": 4, "sed": 8, "elit": 7, "labore": 14, "dolor": 2, "eiusmod": 10, "tempor": 11, "sit": 3, "dolore": 16, "do": 9},
    #                     #  (["aliqua", "magna", "dolore"],["Lorem", "ipsum", "dolor"])
    #                 #  )
    #                 #  ])
    #     # @patch("pcpapillon.core.preprocess.convert_data_to_catboost_pool")
    #     # @patch("pcpapillon.core.predict.get_shap_values")
    # #
    #     # def test_get_prediction_main_contribution(self, data,mock_get_shap_values:Mock,mock_convert_data_to_catboost_pool:Mock):
    #         # mock_get_shap_values.return_value = np.array([[2,3,8,1,9,7,5,6]])
    #         #
    #         model =  model_handler_default.get_model_by_name("compliance", "default")
    #         pool = convert_data_to_catboost_pool(data,model_config_default.catboost_features_types)
    #         assert _get_prediction_main_contribution(model, data) == [9,8,7],[1,2,3]

    @pytest.mark.parametrize(
        ["input_body", "expected_output"],
        [
            (
                {
                    "offer_name": "ninho 4 albums studio + poster",
                    "offer_description": "ninho 4 albums studio + poster",
                    "offer_subcategoryid": "SUPPORT_PHYSIQUE_MUSIQUE",
                    "rayon": "",
                    "macro_rayon": "",
                    "stock_price": 20,
                    "offer_type_label": "rap conscient",
                    "offer_sub_type_label": "17",
                    "author": "ninho",
                    "performer": "judd Law",
                    "semantic_content": "ninho 4 albums studio + poster ninho 4 albums studio + poster rap conscient 17 ninho judd law",
                    "offer_name_embedding": "text embedding",
                    "offer_description_embedding": "text embedding",
                    "image_embedding": "image embedding",
                    "semantic_content_embedding": "text embedding",
                },
                {
                    proba_val,
                    proba_rej,
                    top_val,
                    top_rej,
                },
            )
        ],
    )
    @patch("pcpapillon.core.preprocess.convert_data_to_catboost_pool")
    @patch("pcpapillon.core.predict._get_prediction_main_contribution")
    def test_get_prediction_and_main_contribution(self, data):
        model = model_handler_default.get_model_by_name("compliance", "default")
        pool = convert_data_to_catboost_pool(
            data, model_config_default.catboost_features_types
        )
        data_w_emb = None
        pass
        # assert get_prediction_and_main_contribution(model, data_w_emb, pool) == expected_output
