from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base

class AuctionStatus(StrEnum):
    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    FINISHED = "FINISHED"
    CANCELLED = "CANCELLED"

class LotStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    SOLD = "SOLD"
    UNSOLD = "UNSOLD"

class Auction(Base):
    __tablename__ = "auctions"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    start_at: Mapped[datetime]
    end_at: Mapped[datetime]
    status: Mapped[AuctionStatus] = mapped_column(String(20), default=AuctionStatus.PLANNED)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    lots: Mapped[list["Lot"]] = relationship(back_populates="auction")

class Seller(Base):
    __tablename__ = "sellers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    lots: Mapped[list["Lot"]] = relationship(back_populates="seller")

class Buyer(Base):
    __tablename__ = "buyers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    bids: Mapped[list["Bid"]] = relationship(back_populates="buyer")
    sales: Mapped[list["Sale"]] = relationship(back_populates="buyer")

class Lot(Base):
    __tablename__ = "lots"
    id: Mapped[int] = mapped_column(primary_key=True)
    auction_id: Mapped[int] = mapped_column(ForeignKey("auctions.id"))
    seller_id: Mapped[int] = mapped_column(ForeignKey("sellers.id"))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    starting_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    status: Mapped[LotStatus] = mapped_column(String(20), default=LotStatus.AVAILABLE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    auction: Mapped[Auction] = relationship(back_populates="lots")
    seller: Mapped[Seller] = relationship(back_populates="lots")
    bids: Mapped[list["Bid"]] = relationship(back_populates="lot")
    sale: Mapped["Sale | None"] = relationship(back_populates="lot", uselist=False)

class Bid(Base):
    __tablename__ = "bids"
    id: Mapped[int] = mapped_column(primary_key=True)
    lot_id: Mapped[int] = mapped_column(ForeignKey("lots.id"))
    buyer_id: Mapped[int] = mapped_column(ForeignKey("buyers.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    lot: Mapped[Lot] = relationship(back_populates="bids")
    buyer: Mapped[Buyer] = relationship(back_populates="bids")

class Sale(Base):
    __tablename__ = "sales"
    id: Mapped[int] = mapped_column(primary_key=True)
    lot_id: Mapped[int] = mapped_column(ForeignKey("lots.id"), unique=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey("buyers.id"))
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    sold_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    lot: Mapped[Lot] = relationship(back_populates="sale")
    buyer: Mapped[Buyer] = relationship(back_populates="sales")
