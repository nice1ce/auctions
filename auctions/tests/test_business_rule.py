from decimal import Decimal
import pytest
from fastapi import HTTPException
from app.services import place_bid


def test_bid_must_be_higher():
    class Auction:
        status = "ACTIVE"

    class Lot:
        auction = Auction()
        status = "AVAILABLE"
        starting_price = Decimal("100.00")
        id = 1

    class Bid:
        amount = Decimal("100.00")
        lot_id = 1

    class FakeScalar:
        def scalar(self, _):
            return Decimal("100.00")

    with pytest.raises(HTTPException) as exc:
        place_bid(FakeScalar(), Lot(), Bid())

    assert exc.value.status_code == 409
