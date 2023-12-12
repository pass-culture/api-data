def test_main(client):
    response = client.get(f"/check")
    assert response.status_code == 200
    assert response.json() == "OK"
