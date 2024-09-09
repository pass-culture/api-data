import requests
from utils import is_unique


# Test for similar offers based on offer ID
def test_similar_offers(env):
    url = f"{env['API_URL']}/native/v1/recommendation/similar_offers/{env['OFFER_ID']}"

    response = requests.get(url)
    print(url)
    assert response.status_code == 200
    assert response.elapsed.total_seconds() < 10

    json_response = response.json()
    assert "results" in json_response
    assert isinstance(json_response["results"], list)
    assert len(json_response["results"]) > 0


# Test for similar offers with geolocation
def test_similar_offers_geolocation(env):
    url = f"{env['API_URL']}/native/v1/recommendation/similar_offers/{env['OFFER_ID']}?longitude=2.3688874&latitude=48.8632553"
    print(url)
    response = requests.get(url)

    assert response.status_code == 200

    json_response = response.json()
    assert "results" in json_response
    offer_ids = [offer["id"] for offer in json_response["results"]]
    assert is_unique(offer_ids)
