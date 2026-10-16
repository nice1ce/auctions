"""Unit-тесты бизнес-логики (app/services.py) с граничными значениями.

Тесты написаны так, чтобы «убивать мутантов»: на каждое условие есть случай
по обе стороны границы, поэтому замена `<` на `<=`, `!=` на `==`, `not in`
на `in`, изменение шага ставки и т.п. обнаруживается хотя бы одним тестом.
"""

from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models import Auction, AuctionStatus, Bid, Lot, LotStatus
from app.services import (
    MIN_BID_STEP,
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
from tests.factories import make_auction, make_bid, make_buyer, make_lot, make_seller

ALL_STATUSES = list(AuctionStatus)
OPEN = [AuctionStatus.PLANNED, AuctionStatus.ACTIVE]
CLOSED = [AuctionStatus.FINISHED, AuctionStatus.CANCELLED]


def _status_code(exc_info) -> int:
    return exc_info.value.status_code


# ---- Жизненный цикл аукциона ----------------------------------------------


def test_start_moves_planned_to_active(db_session):
    auction = make_auction(db_session, AuctionStatus.PLANNED)
    assert start_auction(db_session, auction).status == AuctionStatus.ACTIVE


@pytest.mark.parametrize("status", [s for s in ALL_STATUSES if s != "PLANNED"])
def test_start_rejected_unless_planned(db_session, status):
    auction = make_auction(db_session, status)
    with pytest.raises(HTTPException) as exc:
        start_auction(db_session, auction)
    assert _status_code(exc) == 409
    assert auction.status == status


def test_finish_moves_active_to_finished(db_session):
    auction = make_auction(db_session, AuctionStatus.ACTIVE)
    assert finish_auction(db_session, auction).status == AuctionStatus.FINISHED


@pytest.mark.parametrize("status", [s for s in ALL_STATUSES if s != "ACTIVE"])
def test_finish_rejected_unless_active(db_session, status):
    auction = make_auction(db_session, status)
    with pytest.raises(HTTPException) as exc:
        finish_auction(db_session, auction)
    assert _status_code(exc) == 409


@pytest.mark.parametrize("status", OPEN)
def test_cancel_allowed_for_open_auction(db_session, status):
    auction = make_auction(db_session, status)
    assert cancel_auction(db_session, auction).status == AuctionStatus.CANCELLED


@pytest.mark.parametrize("status", CLOSED)
def test_cancel_rejected_for_closed_auction(db_session, status):
    auction = make_auction(db_session, status)
    with pytest.raises(HTTPException) as exc:
        cancel_auction(db_session, auction)
    assert _status_code(exc) == 409


@pytest.mark.parametrize("closer", [finish_auction, cancel_auction])
def test_closing_marks_only_available_lots_of_this_auction_unsold(db_session, closer):
    auction = make_auction(db_session, AuctionStatus.ACTIVE)
    other = make_auction(db_session, AuctionStatus.ACTIVE)
    available = make_lot(db_session, auction)
    sold = make_lot(db_session, auction, status=LotStatus.SOLD)
    foreign = make_lot(db_session, other)

    closer(db_session, auction)

    for lot in (available, sold, foreign):
        db_session.refresh(lot)
    assert available.status == LotStatus.UNSOLD
    assert sold.status == LotStatus.SOLD
    assert foreign.status == LotStatus.AVAILABLE


# ---- Лоты --------------------------------------------------------------------


@pytest.mark.parametrize("status", OPEN)
def test_add_lot_allowed_for_open_auction(db_session, status):
    auction = make_auction(db_session, status)
    lot = add_lot(
        db_session, auction, make_seller(db_session), "Lot", None, Decimal("10.00")
    )
    assert lot.id is not None
    assert lot.status == LotStatus.AVAILABLE
    assert lot.views_count == 0


@pytest.mark.parametrize("status", CLOSED)
def test_add_lot_rejected_for_closed_auction(db_session, status):
    auction = make_auction(db_session, status)
    with pytest.raises(HTTPException) as exc:
        add_lot(db_session, auction, make_seller(db_session), "Lot", None, Decimal("1"))
    assert _status_code(exc) == 409


@pytest.mark.parametrize("status", OPEN)
def test_edit_available_lot_of_open_auction(db_session, status):
    lot = make_lot(db_session, make_auction(db_session, status))
    edited = edit_lot(db_session, lot, {"name": "Renamed"})
    assert edited.name == "Renamed"


@pytest.mark.parametrize("lot_status", [LotStatus.SOLD, LotStatus.UNSOLD])
def test_edit_rejected_for_closed_lot(db_session, lot_status):
    lot = make_lot(
        db_session, make_auction(db_session, AuctionStatus.ACTIVE), status=lot_status
    )
    with pytest.raises(HTTPException) as exc:
        edit_lot(db_session, lot, {"name": "X"})
    assert _status_code(exc) == 409


@pytest.mark.parametrize("status", CLOSED)
def test_edit_rejected_when_auction_closed(db_session, status):
    lot = make_lot(db_session, make_auction(db_session, status))
    with pytest.raises(HTTPException) as exc:
        edit_lot(db_session, lot, {"name": "X"})
    assert _status_code(exc) == 409


def test_remove_lot_without_bids(db_session):
    lot = make_lot(db_session, make_auction(db_session, AuctionStatus.PLANNED))
    lot_id = lot.id
    remove_lot(db_session, lot)
    assert db_session.get(Lot, lot_id) is None


def test_remove_lot_with_bids_rejected(db_session):
    lot = make_lot(db_session, make_auction(db_session, AuctionStatus.ACTIVE))
    make_bid(db_session, lot, make_buyer(db_session), "200.00")
    with pytest.raises(HTTPException) as exc:
        remove_lot(db_session, lot)
    assert _status_code(exc) == 409
    assert db_session.get(Lot, lot.id) is not None


@pytest.mark.parametrize("lot_status", [LotStatus.SOLD, LotStatus.UNSOLD])
def test_remove_closed_lot_rejected(db_session, lot_status):
    lot = make_lot(
        db_session, make_auction(db_session, AuctionStatus.ACTIVE), status=lot_status
    )
    with pytest.raises(HTTPException) as exc:
        remove_lot(db_session, lot)
    assert _status_code(exc) == 409


@pytest.mark.parametrize("status", CLOSED)
def test_remove_lot_of_closed_auction_rejected(db_session, status):
    lot = make_lot(db_session, make_auction(db_session, status))
    with pytest.raises(HTTPException) as exc:
        remove_lot(db_session, lot)
    assert _status_code(exc) == 409


# ---- Ставки: граница «текущая цена + шаг» ---------------------------------


def test_min_bid_step_is_100():
    assert MIN_BID_STEP == Decimal("100.00")


def _bid(lot, buyer, amount):
    return Bid(lot_id=lot.id, buyer_id=buyer.id, amount=Decimal(amount))


@pytest.fixture
def active_lot(db_session):
    return make_lot(
        db_session, make_auction(db_session, AuctionStatus.ACTIVE), "100.00"
    )


def test_first_bid_exactly_start_plus_step_accepted(db_session, active_lot):
    buyer = make_buyer(db_session)
    bid = place_bid(db_session, active_lot, _bid(active_lot, buyer, "200.00"))
    assert bid.id is not None


def test_first_bid_one_kopeck_below_minimum_rejected(db_session, active_lot):
    buyer = make_buyer(db_session)
    with pytest.raises(HTTPException) as exc:
        place_bid(db_session, active_lot, _bid(active_lot, buyer, "199.99"))
    assert _status_code(exc) == 409
    assert "200.00" in exc.value.detail


def test_next_bid_is_measured_from_max_bid_not_start(db_session, active_lot):
    buyer = make_buyer(db_session)
    make_bid(db_session, active_lot, buyer, "500.00")
    make_bid(db_session, active_lot, buyer, "300.00")

    with pytest.raises(HTTPException):
        place_bid(db_session, active_lot, _bid(active_lot, buyer, "599.99"))
    accepted = place_bid(db_session, active_lot, _bid(active_lot, buyer, "600.00"))
    assert accepted.amount == Decimal("600.00")


@pytest.mark.parametrize(
    "status", [AuctionStatus.PLANNED, AuctionStatus.FINISHED, AuctionStatus.CANCELLED]
)
def test_bid_rejected_unless_auction_active(db_session, status):
    lot = make_lot(db_session, make_auction(db_session, status))
    with pytest.raises(HTTPException) as exc:
        place_bid(db_session, lot, _bid(lot, make_buyer(db_session), "1000.00"))
    assert _status_code(exc) == 409


@pytest.mark.parametrize("lot_status", [LotStatus.SOLD, LotStatus.UNSOLD])
def test_bid_rejected_for_closed_lot(db_session, lot_status):
    lot = make_lot(
        db_session, make_auction(db_session, AuctionStatus.ACTIVE), status=lot_status
    )
    with pytest.raises(HTTPException) as exc:
        place_bid(db_session, lot, _bid(lot, make_buyer(db_session), "1000.00"))
    assert _status_code(exc) == 409


# ---- Продажи -----------------------------------------------------------------


def test_sale_at_exactly_starting_price_accepted(db_session, active_lot):
    sale = create_sale(
        db_session, active_lot, make_buyer(db_session), Decimal("100.00")
    )
    assert sale.price == Decimal("100.00")
    db_session.refresh(active_lot)
    assert active_lot.status == LotStatus.SOLD


def test_sale_one_kopeck_below_starting_price_rejected(db_session, active_lot):
    with pytest.raises(HTTPException) as exc:
        create_sale(db_session, active_lot, make_buyer(db_session), Decimal("99.99"))
    assert _status_code(exc) == 422
    assert active_lot.status == LotStatus.AVAILABLE


@pytest.mark.parametrize(
    "status", [AuctionStatus.PLANNED, AuctionStatus.FINISHED, AuctionStatus.CANCELLED]
)
def test_sale_rejected_unless_auction_active(db_session, status):
    lot = make_lot(db_session, make_auction(db_session, status))
    with pytest.raises(HTTPException) as exc:
        create_sale(db_session, lot, make_buyer(db_session), Decimal("500"))
    assert _status_code(exc) == 409


@pytest.mark.parametrize("lot_status", [LotStatus.SOLD, LotStatus.UNSOLD])
def test_sale_rejected_for_closed_lot(db_session, lot_status):
    lot = make_lot(
        db_session, make_auction(db_session, AuctionStatus.ACTIVE), status=lot_status
    )
    with pytest.raises(HTTPException) as exc:
        create_sale(db_session, lot, make_buyer(db_session), Decimal("500"))
    assert _status_code(exc) == 409


# ---- Новая функция Lab 3: счётчик просмотров -------------------------------


def test_increment_lot_views_counts_each_call(db_session, active_lot):
    assert active_lot.views_count == 0
    increment_lot_views(db_session, active_lot)
    lot = increment_lot_views(db_session, active_lot)
    assert lot.views_count == 2


def test_auction_model_default_status_is_planned(db_session):
    auction = make_auction(db_session, AuctionStatus.PLANNED)
    fresh = Auction(name="x", start_at=auction.start_at, end_at=auction.end_at)
    db_session.add(fresh)
    db_session.flush()
    assert fresh.status == AuctionStatus.PLANNED
