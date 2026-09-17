from datetime import datetime, timezone

def test_invalid_auction_dates(client):
    response = client.post(
        "/api/auctions",
        json={
            "name": "Test",
            "start_at": datetime(2026, 1, 2, tzinfo=timezone.utc).isoformat(),
            "end_at": datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(),
        },
    )
    assert response.status_code == 422
    assert "end_at" in response.json()["detail"]
