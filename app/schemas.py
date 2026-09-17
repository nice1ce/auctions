from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field

class AuctionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    start_at: datetime
    end_at: datetime

class AuctionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None

class AuctionRead(AuctionCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: str

class PersonCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320)
    phone: str | None = Field(default=None, max_length=50)

class PersonRead(PersonCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int

class LotCreate(BaseModel):
    auction_id: int
    seller_id: int
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    starting_price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)

class LotUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    starting_price: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)

class LotRead(LotCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: str

class BidCreate(BaseModel):
    buyer_id: int
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)

class BidRead(BidCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    lot_id: int
    created_at: datetime

class SaleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    lot_id: int
    buyer_id: int
    price: Decimal
    sold_at: datetime

class RevenueRead(BaseModel):
    revenue: Decimal
    sales_count: int
