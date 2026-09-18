from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session
from app.models import Auction, AuctionStatus, Bid, Buyer, Lot, LotStatus, Sale, Seller

# Лоты можно добавлять/редактировать/удалять, только пока аукцион ещё не закрыт.
OPEN_AUCTION_STATUSES = (AuctionStatus.PLANNED, AuctionStatus.ACTIVE)


def _close_open_lots(db: Session, auction: Auction) -> None:
    """При завершении или отмене аукциона все непроданные лоты (AVAILABLE)
    закрываются как UNSOLD: дальше по ним нельзя ни делать ставки, ни продавать."""
    db.execute(
        update(Lot)
        .where(Lot.auction_id == auction.id, Lot.status == LotStatus.AVAILABLE)
        .values(status=LotStatus.UNSOLD)
    )


def start_auction(db: Session, auction: Auction) -> Auction:
    if auction.status != AuctionStatus.PLANNED:
        raise HTTPException(409, "Аукцион можно запустить только из PLANNED")
    auction.status = AuctionStatus.ACTIVE
    db.commit()
    db.refresh(auction)
    return auction


def finish_auction(db: Session, auction: Auction) -> Auction:
    if auction.status != AuctionStatus.ACTIVE:
        raise HTTPException(409, "Завершить можно только ACTIVE аукцион")
    auction.status = AuctionStatus.FINISHED
    _close_open_lots(db, auction)
    db.commit()
    db.refresh(auction)
    return auction


def cancel_auction(db: Session, auction: Auction) -> Auction:
    if auction.status not in OPEN_AUCTION_STATUSES:
        raise HTTPException(409, "Отменить можно только PLANNED или ACTIVE аукцион")
    auction.status = AuctionStatus.CANCELLED
    _close_open_lots(db, auction)
    db.commit()
    db.refresh(auction)
    return auction


def add_lot(
    db: Session,
    auction: Auction,
    seller: Seller,
    name: str,
    description: str | None,
    starting_price: Decimal,
) -> Lot:
    if auction.status not in OPEN_AUCTION_STATUSES:
        raise HTTPException(
            409, "Лот можно добавить только в аукцион со статусом PLANNED или ACTIVE"
        )
    lot = Lot(
        auction_id=auction.id,
        seller_id=seller.id,
        name=name,
        description=description,
        starting_price=starting_price,
    )
    db.add(lot)
    db.commit()
    db.refresh(lot)
    return lot


def edit_lot(db: Session, lot: Lot, values: dict) -> Lot:
    if lot.status != LotStatus.AVAILABLE:
        raise HTTPException(409, "Изменять можно только лот в статусе AVAILABLE")
    if lot.auction.status not in OPEN_AUCTION_STATUSES:
        raise HTTPException(409, "Нельзя изменить лот завершённого или отменённого аукциона")
    for key, value in values.items():
        setattr(lot, key, value)
    db.commit()
    db.refresh(lot)
    return lot


def remove_lot(db: Session, lot: Lot) -> None:
    if lot.status != LotStatus.AVAILABLE:
        raise HTTPException(409, "Удалить можно только непроданный лот в статусе AVAILABLE")
    if lot.auction.status not in OPEN_AUCTION_STATUSES:
        raise HTTPException(409, "Нельзя удалить лот завершённого или отменённого аукциона")
    has_bids = db.scalar(select(Bid.id).where(Bid.lot_id == lot.id).limit(1))
    if has_bids:
        raise HTTPException(409, "Нельзя удалить лот, на который уже сделаны ставки")
    db.delete(lot)
    db.commit()


def place_bid(db: Session, lot: Lot, bid: Bid) -> Bid:
    if lot.auction.status != AuctionStatus.ACTIVE:
        raise HTTPException(409, "Ставка принимается только во время ACTIVE аукциона")
    if lot.status != LotStatus.AVAILABLE:
        raise HTTPException(409, "Лот недоступен для ставок")
    current_max = db.scalar(select(func.max(Bid.amount)).where(Bid.lot_id == lot.id))
    minimum = current_max if current_max is not None else lot.starting_price
    if bid.amount <= minimum:
        raise HTTPException(409, f"Ставка должна быть больше текущей цены {minimum:.2f}")
    db.add(bid)
    db.commit()
    db.refresh(bid)
    return bid


def create_sale(db: Session, lot: Lot, buyer: Buyer, price: Decimal) -> Sale:
    """Продажа явно привязывается к лоту: оператор указывает покупателя и цену.
    Продажа возможна только для открытого (AVAILABLE) лота активного аукциона,
    и её создание сразу закрывает лот (переводит в SOLD)."""
    if lot.auction.status != AuctionStatus.ACTIVE:
        raise HTTPException(409, "Продажу можно оформить только во время ACTIVE аукциона")
    if lot.status != LotStatus.AVAILABLE:
        raise HTTPException(409, "Лот уже закрыт: продан или снят с торгов")
    if price < lot.starting_price:
        raise HTTPException(
            422, f"Цена продажи не может быть ниже стартовой цены {lot.starting_price:.2f}"
        )
    sale = Sale(lot_id=lot.id, buyer_id=buyer.id, price=price)
    lot.status = LotStatus.SOLD
    db.add(sale)
    db.commit()
    db.refresh(sale)
    return sale
