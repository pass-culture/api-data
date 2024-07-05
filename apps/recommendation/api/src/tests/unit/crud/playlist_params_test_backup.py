import json

import pytest
from huggy.core.model_selection.model_configuration import parse_model_enpoint
from huggy.schemas.playlist_params import PlaylistParams

model_endpoint = {
    "name": "default_endpoint",
    "description": """""",
    "diversification_params": {"diversication_type": "default"},
    "warn_model_type": {"retrieval": "mix", "ranking": "default"},
    "cold_start_model_type": {"retrieval": "top", "ranking": "default"},
    "fork_params": {"bookings_count": 0, "clicks_count": 0, "favorites_count": 0},
}


class PlaylistParamsTest:
    @pytest.mark.parametrize(
        ["input_params"],
        [
            (
                {
                    "submixing_feature_dict": {
                        "LIVRE_PAPIER": "gtl_id",
                        "CINEMA": "stock_price",
                    }
                },
            )
        ],
    )
    def test_diversfication_params(self, input_params):
        output_playlist_params = PlaylistParams.model_construct(
            submixing_feature_dict=input_params["submixing_feature_dict"]
        )
        assert (
            output_playlist_params.submixing_feature_dict
            == input_params["submixing_feature_dict"]
        )

    @pytest.mark.parametrize(
        ["input_params"],
        [
            ({"modelEndpoint": "default"}, "default"),
            ({"modelEndpoint": "not_existing"}, "default"),
            (
                {"modelEndpoint": json.dumps(model_endpoint).encode("utf-8").hex()},
                "default_endpoint",
            ),
        ],
    )
    def test_model_params(self, input_params, output_name):
        output_playlist_params = PlaylistParams(**input_params)
        model_enpoint = parse_model_enpoint(output_playlist_params)
        model_enpoint.model_name == output_name
