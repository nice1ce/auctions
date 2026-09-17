from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models import Auction, AuctionStatus, Bid, Lot, LotStatus, Sale

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
    db.commit()
    db.refresh(auction)
    return auction

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

def sell_lot(db: Session, lot: Lot) -> Sale:
    if lot.status == LotStatus.SOLD:
        raise HTTPException(409, "Лот уже продан")
    if lot.auction.status != AuctionStatus.ACTIVE:
        raise HTTPException(409, "Продать лот можно только во время ACTIVE аукциона")
    winning_bid = db.scalar(
        select(Bid).where(Bid.lot_id == lot.id)
        .order_by(Bid.amount.desc(), Bid.created_at.desc()).limit(1)
    )
    if winning_bid is None:
        raise HTTPException(409, "Нельзя продать лот без ставок")
    sale = Sale(lot_id=lot.id, buyer_id=winning_bid.buyer_id, price=winning_bid.amount)
    lot.status = LotStatus.SOLD
    db.add(sale)
    db.commit()
    db.refresh(sale)
    return sale
