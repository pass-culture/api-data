import os

import pytest
import requests

ENVIRONMENTS = {
    "dev": {
        "API_URL": "https://backend.testing.passculture.team",
        "OFFER_ID": "440",
    },
    "staging": {
        "API_URL": "https://backend.staging.passculture.team",
        "OFFER_ID": "45093803",
    },
    "production": {
        "API_URL": "https://backend.passculture.team",
        "OFFER_ID": "87654321",
    },
}


def get_environment_config():
    env = os.environ["ENV_SHORT_NAME"]
    defaults = ENVIRONMENTS[env]
    defaults["ACCESS_TOKEN"] = os.environ["ACCESS_TOKEN"]
    return defaults


@pytest.fixture(scope="session")
def env():
    return get_environment_config()


@pytest.fixture(scope="session")
def bearer_token(env):
    url = f"{env['API_URL']}/native/v1/refresh_access_token"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {env['ACCESS_TOKEN']}",
    }
    data = {}
    response = requests.post(url, json=data, headers=headers)
    return response.json()["accessToken"]
