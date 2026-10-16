from datetime import datetime, timezone


def test_invalid_auction_dates(client):
    """Тест проверяет, что аукцион с некорректными датами отвергается."""
    response = client.post(
        "/api/auctions",
        json={
            "name": "Test",
            "start_at": datetime(2026, 1, 2, tzinfo=timezone.utc).isoformat(),
            "end_at": datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(),
        },
    )
    # Ожидаем либо валидацию Pydantic (422), либо ошибку БД (500), но не 201
    assert response.status_code in [422, 500]
