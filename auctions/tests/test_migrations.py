"""Интеграционные тесты миграций Alembic (Lab 3, п. 8–10).

Работают на тестовой БД и после себя возвращают её в состояние «чистая БД
на head», чтобы остальные тесты не зависели от порядка запуска.
"""

from decimal import Decimal

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.db import Base
from tests.conftest import reset_schema

EXPECTED_REVISIONS = [
    "0001_initial",
    "0002_indexes",
    "0003_constraints",
    "0004_users_and_sessions",
    "0005_lot_views_count",
]
APP_TABLES = {"auctions", "sellers", "buyers", "lots", "bids", "sales", "users"}


@pytest.fixture
def migrated_db(test_engine, alembic_config):
    """Отдаёт движок и гарантированно возвращает БД в состояние head."""
    yield test_engine
    reset_schema(test_engine)
    command.upgrade(alembic_config, "head")


def _current_revision(engine):
    with engine.connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()


def test_revision_chain_is_linear_and_has_at_least_three_changes(alembic_config):
    script = ScriptDirectory.from_config(alembic_config)
    assert len(script.get_heads()) == 1, "у миграций должна быть одна голова"
    chain = [rev.revision for rev in script.walk_revisions("base", "heads")]
    assert list(reversed(chain)) == EXPECTED_REVISIONS


def test_clean_database_upgrades_to_head(migrated_db, alembic_config):
    reset_schema(migrated_db)
    assert not set(inspect(migrated_db).get_table_names()) & APP_TABLES

    command.upgrade(alembic_config, "head")

    tables = set(inspect(migrated_db).get_table_names())
    assert APP_TABLES <= tables
    assert _current_revision(migrated_db) == EXPECTED_REVISIONS[-1]


def test_upgrade_of_database_with_existing_data(migrated_db, alembic_config):
    """БД на ревизии 0004 с данными обновляется до head без потери строк."""
    reset_schema(migrated_db)
    command.upgrade(alembic_config, "0004_users_and_sessions")
    with migrated_db.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO auctions (id, name, start_at, end_at, status) VALUES "
                "(1, 'Old', now(), now() + interval '1 day', 'ACTIVE')"
            )
        )
        conn.execute(text("INSERT INTO sellers (id, name, email) VALUES (1,'S','s@x')"))
        conn.execute(
            text(
                "INSERT INTO lots (id, auction_id, seller_id, name, starting_price) "
                "VALUES (1, 1, 1, 'Old lot', 123.45), (2, 1, 1, 'Old lot 2', 10)"
            )
        )

    command.upgrade(alembic_config, "head")

    with migrated_db.connect() as conn:
        rows = conn.execute(
            text("SELECT id, name, starting_price, views_count FROM lots ORDER BY id")
        ).all()
    assert [tuple(r) for r in rows] == [
        (1, "Old lot", Decimal("123.45"), 0),
        (2, "Old lot 2", Decimal("10.00"), 0),
    ]


def test_downgrade_to_base_and_upgrade_again(migrated_db, alembic_config):
    command.downgrade(alembic_config, "base")
    assert not set(inspect(migrated_db).get_table_names()) & APP_TABLES
    command.upgrade(alembic_config, "head")
    assert _current_revision(migrated_db) == EXPECTED_REVISIONS[-1]


def test_views_count_cannot_be_negative(migrated_db):
    with pytest.raises(IntegrityError):
        with migrated_db.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO auctions (id, name, start_at, end_at) VALUES "
                    "(10, 'A', now(), now() + interval '1 day')"
                )
            )
            conn.execute(
                text("INSERT INTO sellers (id, name, email) VALUES (10,'S','s')")
            )
            conn.execute(
                text(
                    "INSERT INTO lots (auction_id, seller_id, name, starting_price, "
                    "views_count) VALUES (10, 10, 'L', 1, -1)"
                )
            )


def test_models_match_migrations(test_engine):
    """Схема после миграций совпадает с моделями: нельзя изменить модель,
    забыв написать миграцию (и наоборот)."""
    with test_engine.connect() as conn:
        ctx = MigrationContext.configure(conn, opts={"compare_type": True})
        diff = compare_metadata(ctx, Base.metadata)
    assert diff == []
