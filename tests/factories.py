"""Фабрики тестовых данных: создают объекты напрямую через ORM-сессию."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.models import Auction, AuctionStatus, Bid, Buyer, Lot, LotStatus, Seller


def make_auction(db, status=AuctionStatus.PLANNED, **kwargs) -> Auction:
    start = datetime.now(timezone.utc) + timedelta(days=1)
    auction = Auction(
        name=kwargs.pop("name", "Auction"),
        start_at=kwargs.pop("start_at", start),
        end_at=kwargs.pop("end_at", start + timedelta(hours=2)),
        status=status,
        **kwargs,
    )
    db.add(auction)
    db.flush()
    return auction


def make_seller(db) -> Seller:
    seller = Seller(name="Seller", email="seller@example.com")
    db.add(seller)
    db.flush()
    return seller


def make_buyer(db, name="Buyer") -> Buyer:
    buyer = Buyer(name=name, email=f"{name.lower()}@example.com")
    db.add(buyer)
    db.flush()
    return buyer


def make_lot(
    db, auction, starting_price="100.00", status=LotStatus.AVAILABLE, seller=None
) -> Lot:
    lot = Lot(
        auction_id=auction.id,
        seller_id=(seller or make_seller(db)).id,
        name="Lot",
        starting_price=Decimal(starting_price),
        status=status,
    )
    db.add(lot)
    db.flush()
    db.refresh(lot)
    return lot


def make_bid(db, lot, buyer, amount) -> Bid:
    bid = Bid(lot_id=lot.id, buyer_id=buyer.id, amount=Decimal(amount))
    db.add(bid)
    db.flush()
    return bid
