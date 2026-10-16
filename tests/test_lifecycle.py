from datetime import datetime, timedelta, timezone


def _create_seller(client):
    response = client.post(
        "/api/sellers", json={"name": "Seller", "email": "seller@test.com"}
    )
    return response.json()


def _create_buyer(client):
    response = client.post(
        "/api/buyers", json={"name": "Buyer", "email": "buyer@test.com"}
    )
    return response.json()


def _create_auction(client):
    start = datetime.now(timezone.utc) + timedelta(days=1)
    end = start + timedelta(days=7)
    response = client.post(
        "/api/auctions",
        json={
            "name": "Auction",
            "start_at": start.isoformat(),
            "end_at": end.isoformat(),
        },
    )
    return response.json()


def _create_lot(client, auction_id, seller_id, starting_price="100.00"):
    response = client.post(
        "/api/lots",
        json={
            "auction_id": auction_id,
            "seller_id": seller_id,
            "name": "Lot",
            "starting_price": starting_price,
        },
    )
    return response


def test_lot_can_be_added_while_planned(client):
    seller = _create_seller(client)
    auction = _create_auction(client)
    response = _create_lot(client, auction["id"], seller["id"])
    assert response.status_code == 201


def test_lot_can_be_added_while_active(client):
    seller = _create_seller(client)
    auction = _create_auction(client)
    client.post(f"/api/auctions/{auction['id']}/start")
    response = _create_lot(client, auction["id"], seller["id"])
    assert response.status_code == 201


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
    lot = _create_lot(client, auction["id"], seller["id"]).json()
    client.post(
        "/api/sales",
        json={"lot_id": lot["id"], "buyer_id": buyer["id"], "price": "150.00"},
    )
    response = client.get(f"/api/lots/{lot['id']}")
    assert response.json()["status"] == "SOLD"


def test_sold_lot_cannot_be_sold_again(client):
    seller = _create_seller(client)
    buyer = _create_buyer(client)
    auction = _create_auction(client)
    client.post(f"/api/auctions/{auction['id']}/start")
    lot = _create_lot(client, auction["id"], seller["id"]).json()
    client.post(
        "/api/sales",
        json={"lot_id": lot["id"], "buyer_id": buyer["id"], "price": "150.00"},
    )
    response = client.post(
        "/api/sales",
        json={"lot_id": lot["id"], "buyer_id": buyer["id"], "price": "200.00"},
    )
    assert response.status_code == 409


def test_sale_price_cannot_be_below_starting_price(client):
    seller = _create_seller(client)
    buyer = _create_buyer(client)
    auction = _create_auction(client)
    client.post(f"/api/auctions/{auction['id']}/start")
    lot = _create_lot(
        client, auction["id"], seller["id"], starting_price="100.00"
    ).json()
    response = client.post(
        "/api/sales",
        json={"lot_id": lot["id"], "buyer_id": buyer["id"], "price": "50.00"},
    )
    assert response.status_code in [422, 409]


def test_sale_requires_active_auction(client):
    seller = _create_seller(client)
    buyer = _create_buyer(client)
    auction = _create_auction(client)
    lot = _create_lot(client, auction["id"], seller["id"]).json()
    response = client.post(
        "/api/sales",
        json={"lot_id": lot["id"], "buyer_id": buyer["id"], "price": "150.00"},
    )
    assert response.status_code == 409


def test_auction_with_lots_cannot_be_deleted(client):
    seller = _create_seller(client)
    auction = _create_auction(client)
    _create_lot(client, auction["id"], seller["id"])
    response = client.delete(f"/api/auctions/{auction['id']}")
    assert response.status_code == 409


def test_bid_below_minimum_step_is_rejected(client):
    seller = _create_seller(client)
    buyer = _create_buyer(client)
    auction = _create_auction(client)
    client.post(f"/api/auctions/{auction['id']}/start")
    lot = _create_lot(
        client, auction["id"], seller["id"], starting_price="100.00"
    ).json()
    response = client.post(
        f"/api/lots/{lot['id']}/bids",
        json={"buyer_id": buyer["id"], "amount": "100.00"},
    )
    assert response.status_code == 409


def test_current_price_reflects_highest_bid_then_sale(client):
    seller = _create_seller(client)
    buyer = _create_buyer(client)
    auction = _create_auction(client)
    client.post(f"/api/auctions/{auction['id']}/start")
    lot = _create_lot(
        client, auction["id"], seller["id"], starting_price="100.00"
    ).json()
    client.post(
        f"/api/lots/{lot['id']}/bids",
        json={"buyer_id": buyer["id"], "amount": "200.00"},
    )
    response = client.get(f"/api/lots/{lot['id']}")
    assert response.json()["current_price"] == 200.00
    client.post(
        "/api/sales",
        json={"lot_id": lot["id"], "buyer_id": buyer["id"], "price": "250.00"},
    )
    response = client.get(f"/api/lots/{lot['id']}")
    assert response.json()["current_price"] == 250.00
