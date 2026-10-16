from fastapi import Cookie, Depends, FastAPI, HTTPException, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import (
    SESSION_COOKIE,
    authenticate_user,
    end_session,
    register_user,
    require_user,
    start_session,
)
from app.config import get_settings
from app.db import get_db
from app.models import Auction, Buyer, Bid, Lot, LotStatus, Sale, Seller, User
from app.schemas import (
    AuctionCreate,
    AuctionRead,
    AuctionUpdate,
    BidCreate,
    BidRead,
    LoginRequest,
    LotCreate,
    LotRead,
    LotUpdate,
    PersonCreate,
    PersonRead,
    RegisterRequest,
    RevenueRead,
    SaleCreate,
    SaleRead,
    UserRead,
)
from app.services import (
    add_lot,
    cancel_auction,
    create_sale,
    edit_lot,
    finish_auction,
    increment_lot_views,
    place_bid,
    remove_lot,
    start_auction,
)

settings = get_settings()
app = FastAPI(title=settings.app_name, version=settings.app_version)
app.mount("/static", StaticFiles(directory="static"), name="static")

# ==================== АУКЦИОНЫ ====================


@app.get("/api/auctions", response_model=list[AuctionRead])
def list_auctions(db: Session = Depends(get_db)):
    return db.scalars(select(Auction).order_by(Auction.start_at.desc())).all()


@app.post("/api/auctions", response_model=AuctionRead, status_code=201)
def create_auction(payload: AuctionCreate, db: Session = Depends(get_db)):
    auction = Auction(**payload.model_dump())
    db.add(auction)
    db.commit()
    db.refresh(auction)
    return auction


@app.get("/api/auctions/{auction_id}", response_model=AuctionRead)
def get_auction(auction_id: int, db: Session = Depends(get_db)):
    auction = db.get(Auction, auction_id)
    if not auction:
        raise HTTPException(404, "Аукцион не найден")
    return auction


@app.patch("/api/auctions/{auction_id}", response_model=AuctionRead)
def update_auction(
    auction_id: int, payload: AuctionUpdate, db: Session = Depends(get_db)
):
    auction = db.get(Auction, auction_id)
    if not auction:
        raise HTTPException(404, "Аукцион не найден")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(auction, key, value)
    db.commit()
    db.refresh(auction)
    return auction


@app.delete("/api/auctions/{auction_id}", status_code=204)
def delete_auction(auction_id: int, db: Session = Depends(get_db)):
    auction = db.get(Auction, auction_id)
    if not auction:
        raise HTTPException(404, "Аукцион не найден")
    has_lots = db.scalar(select(Lot.id).where(Lot.auction_id == auction.id).limit(1))
    if has_lots:
        raise HTTPException(409, "Нельзя удалить аукцион с лотами")
    db.delete(auction)
    db.commit()


@app.post("/api/auctions/{auction_id}/start", response_model=AuctionRead)
def start_auction_route(auction_id: int, db: Session = Depends(get_db)):
    auction = db.get(Auction, auction_id)
    if not auction:
        raise HTTPException(404, "Аукцион не найден")
    return start_auction(db, auction)


@app.post("/api/auctions/{auction_id}/finish", response_model=AuctionRead)
def finish_auction_route(auction_id: int, db: Session = Depends(get_db)):
    auction = db.get(Auction, auction_id)
    if not auction:
        raise HTTPException(404, "Аукцион не найден")
    return finish_auction(db, auction)


@app.post("/api/auctions/{auction_id}/cancel", response_model=AuctionRead)
def cancel_auction_route(auction_id: int, db: Session = Depends(get_db)):
    auction = db.get(Auction, auction_id)
    if not auction:
        raise HTTPException(404, "Аукцион не найден")
    return cancel_auction(db, auction)


# ==================== ПРОДАВЦЫ ====================


@app.get("/api/sellers", response_model=list[PersonRead])
def list_sellers(db: Session = Depends(get_db)):
    return db.scalars(select(Seller).order_by(Seller.name)).all()


@app.post("/api/sellers", response_model=PersonRead, status_code=201)
def create_seller(payload: PersonCreate, db: Session = Depends(get_db)):
    seller = Seller(**payload.model_dump())
    db.add(seller)
    db.commit()
    db.refresh(seller)
    return seller


@app.get("/api/sellers/{seller_id}", response_model=PersonRead)
def get_seller(seller_id: int, db: Session = Depends(get_db)):
    seller = db.get(Seller, seller_id)
    if not seller:
        raise HTTPException(404, "Продавец не найден")
    return seller


# ==================== ПОКУПАТЕЛИ ====================


@app.get("/api/buyers", response_model=list[PersonRead])
def list_buyers(db: Session = Depends(get_db)):
    return db.scalars(select(Buyer).order_by(Buyer.name)).all()


@app.post("/api/buyers", response_model=PersonRead, status_code=201)
def create_buyer(payload: PersonCreate, db: Session = Depends(get_db)):
    buyer = Buyer(**payload.model_dump())
    db.add(buyer)
    db.commit()
    db.refresh(buyer)
    return buyer


@app.get("/api/buyers/{buyer_id}", response_model=PersonRead)
def get_buyer(buyer_id: int, db: Session = Depends(get_db)):
    buyer = db.get(Buyer, buyer_id)
    if not buyer:
        raise HTTPException(404, "Покупатель не найден")
    return buyer


# ==================== ЛОТЫ ====================


@app.get("/api/lots", response_model=list[LotRead])
def list_lots(db: Session = Depends(get_db)):
    lots = db.scalars(select(Lot).order_by(Lot.id)).all()
    result = []
    for lot in lots:
        current_price = lot.starting_price
        if lot.status == LotStatus.SOLD and lot.sale:
            current_price = lot.sale.price
        else:
            max_bid = db.scalar(
                select(func.max(Bid.amount)).where(Bid.lot_id == lot.id)
            )
            if max_bid is not None:
                current_price = max_bid
        lot_dict = LotRead.model_validate(lot).model_dump()
        lot_dict["current_price"] = current_price
        result.append(lot_dict)
    return result


@app.post("/api/lots", response_model=LotRead, status_code=201)
def create_lot(payload: LotCreate, db: Session = Depends(get_db)):
    auction = db.get(Auction, payload.auction_id)
    if not auction:
        raise HTTPException(404, "Аукцион не найден")
    seller = db.get(Seller, payload.seller_id)
    if not seller:
        raise HTTPException(404, "Продавец не найден")
    lot = add_lot(
        db,
        auction,
        seller,
        payload.name,
        payload.description,
        payload.starting_price,
    )
    return lot


@app.get("/api/lots/{lot_id}", response_model=LotRead)
def get_lot(lot_id: int, db: Session = Depends(get_db)):
    lot = db.get(Lot, lot_id)
    if not lot:
        raise HTTPException(404, "Лот не найден")
    current_price = lot.starting_price
    if lot.status == LotStatus.SOLD and lot.sale:
        current_price = lot.sale.price
    else:
        max_bid = db.scalar(select(func.max(Bid.amount)).where(Bid.lot_id == lot.id))
        if max_bid is not None:
            current_price = max_bid
    lot_dict = LotRead.model_validate(lot).model_dump()
    lot_dict["current_price"] = current_price
    return lot_dict


@app.patch("/api/lots/{lot_id}", response_model=LotRead)
def update_lot(lot_id: int, payload: LotUpdate, db: Session = Depends(get_db)):
    lot = db.get(Lot, lot_id)
    if not lot:
        raise HTTPException(404, "Лот не найден")
    return edit_lot(db, lot, payload.model_dump(exclude_unset=True))


@app.delete("/api/lots/{lot_id}", status_code=204)
def delete_lot(lot_id: int, db: Session = Depends(get_db)):
    lot = db.get(Lot, lot_id)
    if not lot:
        raise HTTPException(404, "Лот не найден")
    remove_lot(db, lot)


# ==================== СТАВКИ ====================


@app.get("/api/lots/{lot_id}/bids", response_model=list[BidRead])
def list_bids(lot_id: int, db: Session = Depends(get_db)):
    return db.scalars(
        select(Bid).where(Bid.lot_id == lot_id).order_by(Bid.amount.desc())
    ).all()


@app.post("/api/lots/{lot_id}/bids", response_model=BidRead, status_code=201)
def create_bid(lot_id: int, payload: BidCreate, db: Session = Depends(get_db)):
    lot = db.get(Lot, lot_id)
    if not lot:
        raise HTTPException(404, "Лот не найден")
    buyer = db.get(Buyer, payload.buyer_id)
    if not buyer:
        raise HTTPException(404, "Покупатель не найден")
    bid = Bid(lot_id=lot.id, buyer_id=buyer.id, amount=payload.amount)
    return place_bid(db, lot, bid)


# ==================== ПРОДАЖИ ====================


@app.get("/api/sales", response_model=list[SaleRead])
def list_sales(db: Session = Depends(get_db)):
    return db.scalars(select(Sale).order_by(Sale.sold_at.desc())).all()


@app.post("/api/sales", response_model=SaleRead, status_code=201)
def create_sale_route(payload: SaleCreate, db: Session = Depends(get_db)):
    lot = db.get(Lot, payload.lot_id)
    if not lot:
        raise HTTPException(404, "Лот не найден")
    buyer = db.get(Buyer, payload.buyer_id)
    if not buyer:
        raise HTTPException(404, "Покупатель не найден")
    return create_sale(db, lot, buyer, payload.price)


@app.get("/api/revenue", response_model=RevenueRead)
def get_revenue(db: Session = Depends(get_db)):
    total = db.scalar(select(func.sum(Sale.price))) or 0
    return RevenueRead(total=total)


# ==================== НОВАЯ ФУНКЦИЯ: ПРОСМОТРЫ ЛОТОВ ====================


@app.post("/api/lots/{lot_id}/view")
def view_lot(lot_id: int, db: Session = Depends(get_db)):
    """Новая функция приложения, требующая изменения схемы БД.
    Увеличивает счетчик просмотров лота."""
    lot = db.get(Lot, lot_id)
    if not lot:
        raise HTTPException(404, "Лот не найден")

    updated_lot = increment_lot_views(db, lot)
    return {"lot_id": updated_lot.id, "views_count": updated_lot.views_count}


# ==================== АУТЕНТИФИКАЦИЯ ====================


@app.post("/api/auth/register", status_code=201)
def register(
    payload: RegisterRequest, response: Response, db: Session = Depends(get_db)
):
    user = register_user(db, payload.email, payload.password)
    start_session(db, user, response)
    return UserRead.model_validate(user)


@app.post("/api/auth/login")
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = authenticate_user(db, payload.email, payload.password)
    start_session(db, user, response)
    return UserRead.model_validate(user)


@app.post("/api/auth/logout")
def logout(
    response: Response,
    session_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
):
    if session_token:
        end_session(db, session_token)
    response.delete_cookie(SESSION_COOKIE, httponly=True)
    return {"status": "ok"}


@app.get("/api/auth/me", response_model=UserRead)
def me(user: User = Depends(require_user)):
    return UserRead.model_validate(user)


# ==================== СЛУЖЕБНЫЕ ЭНДПОИНТЫ ====================


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/version")
def version():
    return {"version": settings.app_version}


@app.get("/")
def index():
    return FileResponse("static/index.html")
