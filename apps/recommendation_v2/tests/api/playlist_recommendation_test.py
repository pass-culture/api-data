def test_get_playlist_success(client) -> None:
    """
    Verifies that a user receives their algorithmic recommendation.
    Vertex AI services and tracking are globally mocked in the app.
    """
    user_id = "user_123"
    expected_response = {
        "playlist_recommended_offers": ["1", "2", "3"],
        "params": {
            "reco_origin": "cold_start",
            "model_origin": "default",
            "call_id": "12345678-1234-5678-1234-567812345678",
        },
    }
    expected_response_status_code = 200

    response = client.post(f"/playlist_recommendation/{user_id}", json={})

    assert response.status_code == expected_response_status_code
    assert response.json() == expected_response
