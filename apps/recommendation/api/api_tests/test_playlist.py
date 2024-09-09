import requests
from utils import is_unique


# Test for basic playlist recommendation
def test_playlist_recommendation(env, bearer_token):
    url = f"{env['API_URL']}/native/v1/recommendation/playlist"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {bearer_token}",
    }
    data = {}

    response = requests.post(url, json=data, headers=headers)

    assert response.status_code == 200
    assert response.elapsed.total_seconds() < 10

    json_response = response.json()
    assert json_response is not None
    assert isinstance(json_response, dict)
    assert "playlist_recommended_offers" in json_response
    assert isinstance(json_response["playlist_recommended_offers"], list)
    assert len(json_response["playlist_recommended_offers"]) > 0


# Test playlist recommendation with geolocation (empty body)
def test_playlist_recommendation_geolocation(env, bearer_token):
    url = f"{env['API_URL']}/native/v1/recommendation/playlist?longitude=2.3688874&latitude=48.8632553"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {bearer_token}",
    }
    data = {}

    response = requests.post(url, json=data, headers=headers)

    assert response.status_code == 200
    assert response.elapsed.total_seconds() < 10

    json_response = response.json()
    assert json_response is not None
    assert "playlist_recommended_offers" in json_response
    assert isinstance(json_response["playlist_recommended_offers"], list)
    assert len(json_response["playlist_recommended_offers"]) > 0


# Test playlist recommendation with unique offers check
def test_playlist_recommendation_unique_offer_ids(env, bearer_token):
    url = f"{env['API_URL']}/native/v1/recommendation/playlist"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {bearer_token}",
    }
    data = {}

    response = requests.post(url, json=data, headers=headers)

    assert response.status_code == 200

    json_response = response.json()
    offer_ids = [offer["id"] for offer in json_response["playlist_recommended_offers"]]
    assert is_unique(offer_ids)
