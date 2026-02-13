def test_get_playlist_success(client) -> None:
    user_id = "user_123"
    expected_response = {
        "playlist_recommended_offers": ["1", "2", "3"],
        "params": {"reco_origin": "algo", "model_origin": "model_v1", "call_id": "call_123"},
    }
    expected_response_status_code = 200

    response = client.post(f"/playlist_recommendation/{user_id}")

    assert response.status_code == expected_response_status_code
    assert response.json() == expected_response
