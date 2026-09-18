from datetime import datetime, timedelta, timezone


def _auction_payload(**overrides):
    start = datetime.now(timezone.utc) + timedelta(days=1)
    payload = {
        "name": "Test auction",
        "description": None,
        "start_at": start.isoformat(),
        "end_at": (start + timedelta(hours=2)).isoformat(),
    }
    payload.update(overrides)
    return payload


def _create_auction(client, **overrides):
    response = client.post("/api/auctions", json=_auction_payload(**overrides))
    assert response.status_code == 201, response.text
    return response.json()


def _create_seller(client):
    response = client.post(
        "/api/sellers", json={"name": "Seller", "email": "seller@example.com"}
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_buyer(client):
    response = client.post(
        "/api/buyers", json={"name": "Buyer", "email": "buyer@example.com"}
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_lot(client, auction_id, seller_id, starting_price="100.00"):
    response = client.post(
        "/api/lots",
        json={
            "auction_id": auction_id,
            "seller_id": seller_id,
            "name": "Lot",
            "description": None,
            "starting_price": starting_price,
        },
    )
    return response


def test_lot_can_be_added_while_planned(client):
    seller = _create_seller(client)
    auction = _create_auction(client)
    response = _create_lot(client, auction["id"], seller["id"])
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "AVAILABLE"


def test_lot_can_be_added_while_active(client):
    seller = _create_seller(client)
    auction = _create_auction(client)
    client.post(f"/api/auctions/{auction['id']}/start")
    response = _create_lot(client, auction["id"], seller["id"])
    assert response.status_code == 201, response.text


def test_lot_cannot_be_added_after_finish(client):
    seller = _create_seller(client)
    auction = _create_auction(client)
    client.post(f"/api/auctions/{auction['id']}/start")
    client.post(f"/api/auctions/{auction['id']}/finish")
    response = _create_lot(client, auction["id"], seller["id"])
    assert response.status_code == 409, response.text


def test_lot_cannot_be_added_after_cancel(client):
    seller = _create_seller(client)
    auction = _create_auction(client)
    client.post(f"/api/auctions/{auction['id']}/cancel")
    response = _create_lot(client, auction["id"], seller["id"])
    assert response.status_code == 409, response.text


def test_finish_closes_unsold_lots(client):
    seller = _create_seller(client)
    auction = _create_auction(client)
    client.post(f"/api/auctions/{auction['id']}/start")
    lot = _create_lot(client, auction["id"], seller["id"]).json()

    client.post(f"/api/auctions/{auction['id']}/finish")

    response = client.get(f"/api/lots/{lot['id']}")
    assert response.json()["status"] == "UNSOLD"


def test_cancel_closes_unsold_lots(client):
    seller = _create_seller(client)
    auction = _create_auction(client)
    client.post(f"/api/auctions/{auction['id']}/start")
    lot = _create_lot(client, auction["id"], seller["id"]).json()

    client.post(f"/api/auctions/{auction['id']}/cancel")

    response = client.get(f"/api/lots/{lot['id']}")
    assert response.json()["status"] == "UNSOLD"


def test_sale_closes_the_lot(client):
    seller = _create_seller(client)
    buyer = _create_buyer(client)
    auction = _create_auction(client)
    client.post(f"/api/auctions/{auction['id']}/start")
    lot = _create_lot(client, auction["id"], seller["id"], starting_price="50.00").json()

    response = client.post(
        "/api/sales",
        json={"lot_id": lot["id"], "buyer_id": buyer["id"], "price": "75.00"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["lot_id"] == lot["id"]

    lot_after = client.get(f"/api/lots/{lot['id']}").json()
    assert lot_after["status"] == "SOLD"


def test_sold_lot_cannot_be_sold_again(client):
    seller = _create_seller(client)
    buyer = _create_buyer(client)
    auction = _create_auction(client)
    client.post(f"/api/auctions/{auction['id']}/start")
    lot = _create_lot(client, auction["id"], seller["id"], starting_price="50.00").json()
    client.post(
        "/api/sales",
        json={"lot_id": lot["id"], "buyer_id": buyer["id"], "price": "75.00"},
    )

    response = client.post(
        "/api/sales",
        json={"lot_id": lot["id"], "buyer_id": buyer["id"], "price": "80.00"},
    )
    assert response.status_code == 409, response.text


def test_sale_price_cannot_be_below_starting_price(client):
    seller = _create_seller(client)
    buyer = _create_buyer(client)
    auction = _create_auction(client)
    client.post(f"/api/auctions/{auction['id']}/start")
    lot = _create_lot(client, auction["id"], seller["id"], starting_price="50.00").json()

    response = client.post(
        "/api/sales",
        json={"lot_id": lot["id"], "buyer_id": buyer["id"], "price": "10.00"},
    )
    assert response.status_code == 422, response.text


def test_sale_requires_active_auction(client):
    seller = _create_seller(client)
    buyer = _create_buyer(client)
    auction = _create_auction(client)
    lot = _create_lot(client, auction["id"], seller["id"], starting_price="50.00").json()

    response = client.post(
        "/api/sales",
        json={"lot_id": lot["id"], "buyer_id": buyer["id"], "price": "60.00"},
    )
    assert response.status_code == 409, response.text


def test_auction_with_lots_cannot_be_deleted(client):
    seller = _create_seller(client)
    auction = _create_auction(client)
    _create_lot(client, auction["id"], seller["id"])

    response = client.delete(f"/api/auctions/{auction['id']}")
    assert response.status_code == 409, response.text
