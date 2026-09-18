from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import Auction, Buyer, Bid, Lot, Sale, Seller
from app.schemas import (
    AuctionCreate,
    AuctionRead,
    AuctionUpdate,
    BidCreate,
    BidRead,
    LotCreate,
    LotRead,
    LotUpdate,
    PersonCreate,
    PersonRead,
    RevenueRead,
    SaleCreate,
    SaleRead,
)
from app.services import (
    add_lot,
    cancel_auction,
    create_sale,
    edit_lot,
    finish_auction,
    place_bid,
    remove_lot,
    start_auction,
)

settings = get_settings()
app = FastAPI(title=settings.app_name, version=settings.app_version)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/version")
def version():
    return {"version": settings.app_version}


@app.get("/")
def index():
    return FileResponse("static/index.html")


@app.get("/api/auctions", response_model=list[AuctionRead])
def list_auctions(db: Session = Depends(get_db)):
    return db.scalars(select(Auction).order_by(Auction.id.desc())).all()


@app.get("/api/auctions/{auction_id}", response_model=AuctionRead)
def get_auction(auction_id: int, db: Session = Depends(get_db)):
    auction = db.get(Auction, auction_id)
    if not auction:
        raise HTTPException(404, "Аукцион не найден")
    return auction


@app.post("/api/auctions", response_model=AuctionRead, status_code=201)
def create_auction(data: AuctionCreate, db: Session = Depends(get_db)):
    if data.end_at <= data.start_at:
        raise HTTPException(422, "end_at должен быть позже start_at")
    auction = Auction(**data.model_dump())
    db.add(auction)
    db.commit()
    db.refresh(auction)
    return auction


@app.patch("/api/auctions/{auction_id}", response_model=AuctionRead)
def update_auction(auction_id: int, data: AuctionUpdate, db: Session = Depends(get_db)):
    auction = db.get(Auction, auction_id)
    if not auction:
        raise HTTPException(404, "Аукцион не найден")
    values = data.model_dump(exclude_unset=True)
    start = values.get("start_at", auction.start_at)
    end = values.get("end_at", auction.end_at)
    if end <= start:
        raise HTTPException(422, "end_at должен быть позже start_at")
    for key, value in values.items():
        setattr(auction, key, value)
    db.commit()
    db.refresh(auction)
    return auction


@app.delete("/api/auctions/{auction_id}", status_code=204)
def delete_auction(auction_id: int, db: Session = Depends(get_db)):
    auction = db.get(Auction, auction_id)
    if not auction:
        raise HTTPException(404, "Аукцион не найден")
    if db.scalar(select(Lot.id).where(Lot.auction_id == auction_id).limit(1)):
        raise HTTPException(409, "Нельзя удалить аукцион, у которого уже есть лоты")
    db.delete(auction)
    db.commit()


@app.post("/api/auctions/{auction_id}/start", response_model=AuctionRead)
def api_start_auction(auction_id: int, db: Session = Depends(get_db)):
    auction = db.get(Auction, auction_id)
    if not auction:
        raise HTTPException(404, "Аукцион не найден")
    return start_auction(db, auction)


@app.post("/api/auctions/{auction_id}/finish", response_model=AuctionRead)
def api_finish_auction(auction_id: int, db: Session = Depends(get_db)):
    auction = db.get(Auction, auction_id)
    if not auction:
        raise HTTPException(404, "Аукцион не найден")
    return finish_auction(db, auction)


@app.post("/api/auctions/{auction_id}/cancel", response_model=AuctionRead)
def api_cancel_auction(auction_id: int, db: Session = Depends(get_db)):
    auction = db.get(Auction, auction_id)
    if not auction:
        raise HTTPException(404, "Аукцион не найден")
    return cancel_auction(db, auction)


@app.get("/api/sellers", response_model=list[PersonRead])
def list_sellers(db: Session = Depends(get_db)):
    return db.scalars(select(Seller).order_by(Seller.id.desc())).all()


@app.post("/api/sellers", response_model=PersonRead, status_code=201)
def create_seller(data: PersonCreate, db: Session = Depends(get_db)):
    seller = Seller(**data.model_dump())
    db.add(seller)
    db.commit()
    db.refresh(seller)
    return seller


@app.patch("/api/sellers/{seller_id}", response_model=PersonRead)
def update_seller(seller_id: int, data: PersonCreate, db: Session = Depends(get_db)):
    seller = db.get(Seller, seller_id)
    if not seller:
        raise HTTPException(404, "Продавец не найден")
    for key, value in data.model_dump().items():
        setattr(seller, key, value)
    db.commit()
    db.refresh(seller)
    return seller


@app.get("/api/buyers", response_model=list[PersonRead])
def list_buyers(db: Session = Depends(get_db)):
    return db.scalars(select(Buyer).order_by(Buyer.id.desc())).all()


@app.post("/api/buyers", response_model=PersonRead, status_code=201)
def create_buyer(data: PersonCreate, db: Session = Depends(get_db)):
    buyer = Buyer(**data.model_dump())
    db.add(buyer)
    db.commit()
    db.refresh(buyer)
    return buyer


@app.patch("/api/buyers/{buyer_id}", response_model=PersonRead)
def update_buyer(buyer_id: int, data: PersonCreate, db: Session = Depends(get_db)):
    buyer = db.get(Buyer, buyer_id)
    if not buyer:
        raise HTTPException(404, "Покупатель не найден")
    for key, value in data.model_dump().items():
        setattr(buyer, key, value)
    db.commit()
    db.refresh(buyer)
    return buyer


@app.get("/api/lots", response_model=list[LotRead])
def list_lots(db: Session = Depends(get_db)):
    return db.scalars(select(Lot).order_by(Lot.id.desc())).all()


@app.get("/api/lots/{lot_id}", response_model=LotRead)
def get_lot(lot_id: int, db: Session = Depends(get_db)):
    lot = db.get(Lot, lot_id)
    if not lot:
        raise HTTPException(404, "Лот не найден")
    return lot


@app.post("/api/lots", response_model=LotRead, status_code=201)
def create_lot(data: LotCreate, db: Session = Depends(get_db)):
    auction = db.get(Auction, data.auction_id)
    if not auction:
        raise HTTPException(404, "Аукцион не найден")
    seller = db.get(Seller, data.seller_id)
    if not seller:
        raise HTTPException(404, "Продавец не найден")
    return add_lot(
        db, auction, seller, data.name, data.description, data.starting_price
    )


@app.patch("/api/lots/{lot_id}", response_model=LotRead)
def update_lot(lot_id: int, data: LotUpdate, db: Session = Depends(get_db)):
    lot = db.get(Lot, lot_id)
    if not lot:
        raise HTTPException(404, "Лот не найден")
    return edit_lot(db, lot, data.model_dump(exclude_unset=True))


@app.delete("/api/lots/{lot_id}", status_code=204)
def delete_lot(lot_id: int, db: Session = Depends(get_db)):
    lot = db.get(Lot, lot_id)
    if not lot:
        raise HTTPException(404, "Лот не найден")
    remove_lot(db, lot)


@app.get("/api/lots/{lot_id}/bids", response_model=list[BidRead])
def list_bids(lot_id: int, db: Session = Depends(get_db)):
    if not db.get(Lot, lot_id):
        raise HTTPException(404, "Лот не найден")
    return db.scalars(
        select(Bid).where(Bid.lot_id == lot_id).order_by(Bid.amount.desc())
    ).all()


@app.post("/api/lots/{lot_id}/bids", response_model=BidRead, status_code=201)
def create_bid(lot_id: int, data: BidCreate, db: Session = Depends(get_db)):
    lot = db.get(Lot, lot_id)
    if not lot:
        raise HTTPException(404, "Лот не найден")
    if not db.get(Buyer, data.buyer_id):
        raise HTTPException(404, "Покупатель не найден")
    return place_bid(db, lot, Bid(lot_id=lot_id, **data.model_dump()))


@app.post("/api/sales", response_model=SaleRead, status_code=201)
def api_create_sale(data: SaleCreate, db: Session = Depends(get_db)):
    lot = db.get(Lot, data.lot_id)
    if not lot:
        raise HTTPException(404, "Лот не найден")
    buyer = db.get(Buyer, data.buyer_id)
    if not buyer:
        raise HTTPException(404, "Покупатель не найден")
    return create_sale(db, lot, buyer, data.price)


@app.get("/api/sales", response_model=list[SaleRead])
def list_sales(db: Session = Depends(get_db)):
    return db.scalars(select(Sale).order_by(Sale.id.desc())).all()


@app.get("/api/sales/{sale_id}", response_model=SaleRead)
def get_sale(sale_id: int, db: Session = Depends(get_db)):
    sale = db.get(Sale, sale_id)
    if not sale:
        raise HTTPException(404, "Продажа не найдена")
    return sale


@app.get("/api/reports/revenue", response_model=RevenueRead)
def revenue_report(db: Session = Depends(get_db)):
    revenue = db.scalar(select(func.coalesce(func.sum(Sale.price), 0))) or 0
    sales_count = db.scalar(select(func.count(Sale.id))) or 0
    return {"revenue": revenue, "sales_count": sales_count}
