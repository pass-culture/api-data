import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock, call
from pcpapillon.core.preprocess import prepare_features
from pcpapillon.utils.configs import configs
from pcpapillon.core.extract_embedding import extract_embedding
from tests.conftest import config_handler,api_config, model_config_default, model_handler_default

class PreprocessTest:
    @pytest.mark.parametrize(
        ["input_body", "expected_preprocess"],
        [
            (
                {
                    "offer_id": "420",
                    "offer_name": "ninho 4 albums studio + poster",
                    "offer_description": "ninho 4 albums studio + poster",
                    "offer_subcategoryid": "SUPPORT_PHYSIQUE_MUSIQUE",
                    "rayon": None,
                    "macro_rayon": "",
                    "stock_price": "20",
                    "image_url": "https://storage.googleapis.com/passculture-metier-prod-production-assets-fine-grained/thumbs/products/9YKMS",
                    "offer_type_label": "rap conscient",
                    "offer_sub_type_label": "17",
                    "author": "ninho",
                    "performer": "judd Law",
                },
                {
                    "offer_name": "ninho 4 albums studio + poster",
                    "offer_description": "ninho 4 albums studio + poster",
                    "offer_subcategoryid": "SUPPORT_PHYSIQUE_MUSIQUE",
                    "rayon": "",
                    "macro_rayon": "",
                    "stock_price": 20,
                    "image_url": "https://storage.googleapis.com/passculture-metier-prod-production-assets-fine-grained/thumbs/products/9YKMS",
                    "offer_type_label": "rap conscient",
                    "offer_sub_type_label": "17",
                    "author": "ninho",
                    "performer": "judd Law",
                    "semantic_content": "ninho 4 albums studio + poster ninho 4 albums studio + poster rap conscient 17 ninho judd law"
                },

            )])
    def test_prepare_features(self, input_body, expected_preprocess):

        assert prepare_features(input_body,api_config.preprocess_features_type) == expected_preprocess

    @pytest.mark.parametrize(
                    ["expected_preprocess","expected_data_embedding"],
        [
            (
                {
                    "offer_name": "ninho 4 albums studio + poster",
                    "offer_description": "ninho 4 albums studio + poster",
                    "offer_subcategoryid": "SUPPORT_PHYSIQUE_MUSIQUE",
                    "rayon": "",
                    "macro_rayon": "",
                    "stock_price": 20,
                    "image_url": "https://storage.googleapis.com/passculture-metier-prod-production-assets-fine-grained/thumbs/products/9YKMS",
                    "offer_type_label": "rap conscient",
                    "offer_sub_type_label": "17",
                    "author": "ninho",
                    "performer": "judd Law",
                    "semantic_content": "ninho 4 albums studio + poster ninho 4 albums studio + poster rap conscient 17 ninho judd law"
                },
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
                    "offer_name_embedding":"text embedding",
                    "offer_description_embedding":"text embedding",
                    "image_embedding":"image embedding",
                    "semantic_content_embedding":"text embedding",
                },

            )
        ],
    )
    

    @patch("pcpapillon.core.extract_embedding._encode_img_from_url")

    @patch("pcpapillon.core.extract_embedding._encode_from_feature")

    def test_extract_embedding(self,encode_from_feature_mock: Mock,encode_from_url_mock: Mock,expected_preprocess,expected_data_embedding):
        prepoc_models = {}
        for feature_type in model_config_default.pre_trained_model_for_embedding_extraction.keys():
            prepoc_models[feature_type] = model_handler_default.get_model_by_name(feature_type)
        encode_from_feature_mock.return_value="text embedding"
        encode_from_url_mock.return_value="image embedding"
        output = extract_embedding(expected_preprocess,api_config.features_to_extract_embedding,prepoc_models)
        assert (output == expected_data_embedding)
