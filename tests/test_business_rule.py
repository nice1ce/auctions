from datetime import datetime
from decimal import Decimal
import pytest
from fastapi import HTTPException
from app.models import Auction, AuctionStatus, Bid, Buyer, Lot, LotStatus, Seller
from app.services import place_bid, create_sale


def test_bid_must_be_strictly_higher_than_current_price_plus_step(db_session):
    """Ставка должна быть не меньше текущей цены + 100."""
    auction = Auction(
        name="Test",
        start_at=datetime(2026, 1, 1),
        end_at=datetime(2026, 12, 31),
        status=AuctionStatus.ACTIVE,
    )
    db_session.add(auction)
    db_session.commit()

    seller = Seller(name="Seller", email="s@test.com")
    db_session.add(seller)
    db_session.commit()

    lot = Lot(
        auction_id=auction.id,
        seller_id=seller.id,
        name="Lot",
        starting_price=Decimal("100.00"),
        status=LotStatus.AVAILABLE,
    )
    db_session.add(lot)
    db_session.commit()

    buyer = Buyer(name="Buyer", email="b@test.com")
    db_session.add(buyer)
    db_session.commit()

    # Попытка сделать ставку ровно на текущую цену (должно быть минимум 200.00)
    bid = Bid(lot_id=lot.id, buyer_id=buyer.id, amount=Decimal("100.00"))

    with pytest.raises(HTTPException) as exc_info:
        place_bid(db_session, lot, bid)

    assert exc_info.value.status_code == 409
    assert "должна быть не меньше" in str(exc_info.value.detail)


def test_cannot_sell_already_sold_lot(db_session):
    """Попытка продать уже проданный лот должна вызывать ошибку."""
    auction = Auction(
        name="Test",
        start_at=datetime(2026, 1, 1),
        end_at=datetime(2026, 12, 31),
        status=AuctionStatus.ACTIVE,
    )
    db_session.add(auction)
    db_session.commit()

    seller = Seller(name="Seller", email="s@test.com")
    db_session.add(seller)
    db_session.commit()

    # Лот уже имеет статус SOLD
    lot = Lot(
        auction_id=auction.id,
        seller_id=seller.id,
        name="Lot",
        starting_price=Decimal("100.00"),
        status=LotStatus.SOLD,
    )
    db_session.add(lot)
    db_session.commit()

    buyer = Buyer(name="Buyer", email="b@test.com")
    db_session.add(buyer)
    db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        create_sale(db_session, lot, buyer, Decimal("150.00"))

    assert exc_info.value.status_code == 409
    assert "уже закрыт" in str(exc_info.value.detail)


def test_lot_view_count_increments(client, db_session):
    """Интеграционный тест новой функции (счетчик просмотров)."""
    auction = Auction(
        name="Test",
        start_at=datetime(2026, 1, 1),
        end_at=datetime(2026, 12, 31),
        status=AuctionStatus.PLANNED,
    )
    db_session.add(auction)
    db_session.commit()

    seller = Seller(name="Seller", email="s@test.com")
    db_session.add(seller)
    db_session.commit()

    lot = Lot(
        auction_id=auction.id,
        seller_id=seller.id,
        name="Lot",
        starting_price=Decimal("100.00"),
        status=LotStatus.AVAILABLE,
        views_count=0,
    )
    db_session.add(lot)
    db_session.commit()

    response = client.post(f"/api/lots/{lot.id}/view")
    assert response.status_code == 200
    assert response.json()["views_count"] == 1

    # Проверяем, что данные реально сохранились в БД
    db_session.refresh(lot)
    assert lot.views_count == 1
