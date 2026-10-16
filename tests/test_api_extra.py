"""Интеграционные тесты HTTP API + БД: ошибочные данные, граничные случаи,
отчёт по выручке и новая функция Lab 3 (счётчик просмотров лота)."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import auth as auth_module
from app.auth import SESSION_COOKIE, hash_password, verify_password
from app.main import app
from app.models import UserSession


def _auction(client, **overrides):
    start = datetime.now(timezone.utc) + timedelta(days=1)
    payload = {
        "name": "Auction",
        "start_at": start.isoformat(),
        "end_at": (start + timedelta(hours=1)).isoformat(),
    }
    payload.update(overrides)
    return client.post("/api/auctions", json=payload)


def _person(client, kind):
    response = client.post(f"/api/{kind}", json={"name": kind, "email": "a@b.cd"})
    assert response.status_code == 201, response.text
    return response.json()


def _active_lot(client, starting_price="100.00"):
    auction = _auction(client).json()
    client.post(f"/api/auctions/{auction['id']}/start")
    seller = _person(client, "sellers")
    response = client.post(
        "/api/lots",
        json={
            "auction_id": auction["id"],
            "seller_id": seller["id"],
            "name": "Lot",
            "starting_price": starting_price,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


# ---- Новая функция: просмотры лота ------------------------------------------


def test_lot_views_counter_increments_and_is_returned_in_lot(client):
    lot = _active_lot(client)
    assert lot["views_count"] == 0

    first = client.post(f"/api/lots/{lot['id']}/view")
    second = client.post(f"/api/lots/{lot['id']}/view")

    assert first.status_code == 200, first.text
    assert first.json() == {"lot_id": lot["id"], "views_count": 1}
    assert second.json()["views_count"] == 2
    assert client.get(f"/api/lots/{lot['id']}").json()["views_count"] == 2


def test_lot_views_for_missing_lot_is_404(client):
    assert client.post("/api/lots/999999/view").status_code == 404


# ---- Ошибочные данные и граничные случаи ------------------------------------


def test_auction_with_equal_start_and_end_is_rejected(client):
    moment = datetime.now(timezone.utc).isoformat()
    response = _auction(client, start_at=moment, end_at=moment)
    assert response.status_code == 422, response.text


def test_auction_end_one_second_after_start_is_accepted(client):
    start = datetime.now(timezone.utc)
    response = _auction(
        client,
        start_at=start.isoformat(),
        end_at=(start + timedelta(seconds=1)).isoformat(),
    )
    assert response.status_code == 201, response.text


def test_patch_auction_cannot_break_dates(client):
    auction = _auction(client).json()
    response = client.patch(
        f"/api/auctions/{auction['id']}", json={"end_at": auction["start_at"]}
    )
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("name", ["", "x" * 201])
def test_auction_name_length_is_validated(client, name):
    assert _auction(client, name=name).status_code == 422


@pytest.mark.parametrize("price", ["0", "-1.00", "1.001", "abc"])
def test_invalid_lot_starting_price_is_rejected(client, price):
    auction = _auction(client).json()
    seller = _person(client, "sellers")
    response = client.post(
        "/api/lots",
        json={
            "auction_id": auction["id"],
            "seller_id": seller["id"],
            "name": "Lot",
            "starting_price": price,
        },
    )
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("amount", ["0", "-100"])
def test_non_positive_bid_is_rejected(client, amount):
    lot = _active_lot(client)
    buyer = _person(client, "buyers")
    response = client.post(
        f"/api/lots/{lot['id']}/bids", json={"buyer_id": buyer["id"], "amount": amount}
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "method,url,body",
    [
        ("get", "/api/auctions/999999", None),
        ("get", "/api/lots/999999", None),
        ("get", "/api/lots/999999/bids", None),
        ("get", "/api/sales/999999", None),
        ("post", "/api/auctions/999999/start", None),
        ("post", "/api/auctions/999999/finish", None),
        ("post", "/api/auctions/999999/cancel", None),
        ("delete", "/api/auctions/999999", None),
        ("delete", "/api/lots/999999", None),
        ("patch", "/api/sellers/999999", {"name": "n", "email": "a@b.cd"}),
        ("patch", "/api/buyers/999999", {"name": "n", "email": "a@b.cd"}),
    ],
)
def test_missing_entities_return_404(client, method, url, body):
    kwargs = {"json": body} if body is not None else {}
    assert getattr(client, method)(url, **kwargs).status_code == 404


def test_lot_with_unknown_auction_or_seller_is_404(client):
    auction = _auction(client).json()
    seller = _person(client, "sellers")
    base = {"name": "Lot", "starting_price": "10.00"}
    no_auction = client.post(
        "/api/lots", json={**base, "auction_id": 999999, "seller_id": seller["id"]}
    )
    no_seller = client.post(
        "/api/lots", json={**base, "auction_id": auction["id"], "seller_id": 999999}
    )
    assert no_auction.status_code == 404
    assert no_seller.status_code == 404


def test_bid_and_sale_with_unknown_buyer_are_404(client):
    lot = _active_lot(client)
    bid = client.post(
        f"/api/lots/{lot['id']}/bids", json={"buyer_id": 999999, "amount": "500"}
    )
    sale = client.post(
        "/api/sales", json={"lot_id": lot["id"], "buyer_id": 999999, "price": "500"}
    )
    assert bid.status_code == 404
    assert sale.status_code == 404


def test_lot_without_bids_can_be_deleted(client):
    auction = _auction(client).json()
    seller = _person(client, "sellers")
    lot = client.post(
        "/api/lots",
        json={
            "auction_id": auction["id"],
            "seller_id": seller["id"],
            "name": "Lot",
            "starting_price": "10.00",
        },
    ).json()
    assert client.delete(f"/api/lots/{lot['id']}").status_code == 204
    assert client.get(f"/api/lots/{lot['id']}").status_code == 404


def test_empty_auction_can_be_deleted(client):
    auction = _auction(client).json()
    assert client.delete(f"/api/auctions/{auction['id']}").status_code == 204


# ---- Отчёт по выручке ---------------------------------------------------------


def test_revenue_is_sum_of_sales(client):
    empty = client.get("/api/reports/revenue").json()
    assert float(empty["revenue"]) == 0
    assert empty["sales_count"] == 0
    buyer = _person(client, "buyers")
    for price in ("150.00", "250.50"):
        lot = _active_lot(client, starting_price="100.00")
        client.post(
            "/api/sales",
            json={"lot_id": lot["id"], "buyer_id": buyer["id"], "price": price},
        )
    report = client.get("/api/reports/revenue").json()
    assert float(report["revenue"]) == 400.50
    assert report["sales_count"] == 2
    assert len(client.get("/api/sales").json()) == 2


# ---- Аутентификация: граничные случаи ---------------------------------------


def test_password_hash_roundtrip():
    hashed = hash_password("correct-horse")
    assert hashed != "correct-horse"
    assert verify_password("correct-horse", hashed)
    assert not verify_password("wrong-horse", hashed)
    assert not verify_password("anything", "not-a-bcrypt-hash")


def test_email_is_normalized_on_register_and_login(client):
    client.post(
        "/api/auth/register",
        json={"email": "  Mixed@Case.COM ", "password": "correct-horse"},
    )
    client.cookies.clear()
    response = client.post(
        "/api/auth/login", json={"email": "mixed@case.com", "password": "correct-horse"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["email"] == "mixed@case.com"


@pytest.mark.parametrize("length,status", [(7, 422), (8, 201)])
def test_password_length_boundary(client, length, status):
    response = client.post(
        "/api/auth/register",
        json={"email": f"len{length}@example.com", "password": "p" * length},
    )
    assert response.status_code == status


def test_expired_session_is_not_accepted(client, db_session):
    client.post(
        "/api/auth/register",
        json={"email": "expire@example.com", "password": "correct-horse"},
    )
    token = client.cookies.get(SESSION_COOKIE)
    session = db_session.get(UserSession, token)
    session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()
    assert client.get("/api/auth/me").status_code == 401


def test_session_cookie_is_httponly(client):
    response = client.post(
        "/api/auth/register",
        json={"email": "cookie@example.com", "password": "correct-horse"},
    )
    set_cookie = response.headers["set-cookie"].lower()
    assert f"{SESSION_COOKIE}=" in set_cookie
    assert "httponly" in set_cookie
    assert "samesite=lax" in set_cookie


def test_logout_removes_only_own_session_on_server(client, db_session):
    other = TestClient(app)
    other.post(
        "/api/auth/register",
        json={"email": "other@example.com", "password": "correct-horse"},
    )
    client.post(
        "/api/auth/register",
        json={"email": "me@example.com", "password": "correct-horse"},
    )
    my_token = client.cookies.get(SESSION_COOKIE)
    other_token = other.cookies.get(SESSION_COOKIE)

    assert client.post("/api/auth/logout").status_code == 204

    assert db_session.get(UserSession, my_token) is None
    assert db_session.get(UserSession, other_token) is not None
    assert other.get("/api/auth/me").status_code == 200


def test_session_is_valid_until_exact_expiry_moment(client, db_session, monkeypatch):
    client.post(
        "/api/auth/register",
        json={"email": "edge@example.com", "password": "correct-horse"},
    )
    session = db_session.get(UserSession, client.cookies.get(SESSION_COOKIE))
    moment = session.expires_at

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return moment

    monkeypatch.setattr(auth_module, "datetime", FrozenDatetime)
    assert client.get("/api/auth/me").status_code == 200
