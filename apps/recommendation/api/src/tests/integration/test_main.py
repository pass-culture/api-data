def test_main(client):
    response = client.get("/health/api")
    assert response.status_code == 200
    assert response.json() == "OK"
