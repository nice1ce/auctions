"""Тестовая конфигурация (Lab 3, п. 6).

* Тесты работают ТОЛЬКО с отдельной тестовой БД из TEST_DATABASE_URL и
  отказываются запускаться, если она совпадает с рабочей DATABASE_URL.
* Схема тестовой БД каждый прогон создаётся с нуля реальными миграциями
  Alembic (а не Base.metadata.create_all), поэтому тесты проверяют ту же
  схему, что будет в эксплуатации, включая CHECK-ограничения.
* Каждый тест выполняется внутри внешней транзакции, которая откатывается
  после теста: данные тестов не видны друг другу и не остаются в БД.
* Пропуск тестов запрещён (п. 14): skip/skipif/xfail роняют прогон.
"""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.db import get_db
from app.main import app

ROOT = Path(__file__).resolve().parent.parent
BANNED_OUTCOMES = ("skipped", "xfailed", "xpassed")


def _test_database_url() -> str:
    settings = get_settings()
    url = settings.test_database_url
    if not url:
        pytest.exit("TEST_DATABASE_URL не задан (см. .env.example)", returncode=4)
    if make_url(url).database == make_url(settings.database_url).database:
        pytest.exit(
            "TEST_DATABASE_URL указывает на рабочую БД — тесты её очистят. "
            "Задайте отдельную БД, например auction_test.",
            returncode=4,
        )
    return url


def _ensure_database_exists(url: str) -> None:
    """Создаёт тестовую БД, если её ещё нет (нужны права CREATEDB)."""
    target = make_url(url)
    admin = create_engine(
        target.set(database="postgres"),
        isolation_level="AUTOCOMMIT",
        poolclass=NullPool,
    )
    with admin.connect() as conn:
        exists = conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": target.database},
        )
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{target.database}"'))
    admin.dispose()


def make_alembic_config(url: str) -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.attributes["database_url"] = url
    cfg.attributes["configure_logger"] = False
    return cfg


def reset_schema(engine) -> None:
    """Полностью очищает схему public (чистая БД без таблиц)."""
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))


@pytest.fixture(scope="session")
def test_database_url() -> str:
    url = _test_database_url()
    _ensure_database_exists(url)
    return url


@pytest.fixture(scope="session")
def alembic_config(test_database_url) -> Config:
    return make_alembic_config(test_database_url)


@pytest.fixture(scope="session")
def test_engine(test_database_url, alembic_config):
    engine = create_engine(test_database_url, poolclass=NullPool)
    reset_schema(engine)
    command.upgrade(alembic_config, "head")
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(test_engine):
    connection = test_engine.connect()
    transaction = connection.begin()
    # create_savepoint: commit() внутри приложения фиксирует только SAVEPOINT,
    # а внешняя транзакция откатывается после теста.
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield session
    finally:
        app.dependency_overrides.pop(get_db, None)
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db_session):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def api_version():
    return get_settings().app_version


# ---- П. 14: запрет на пропуск тестов --------------------------------------


def pytest_collection_modifyitems(config, items):
    for item in items:
        for marker in ("skip", "skipif", "xfail"):
            if item.get_closest_marker(marker):
                raise pytest.UsageError(
                    f"{item.nodeid}: маркер @{marker} запрещён политикой проекта "
                    "(CONTRIBUTING.md, раздел «Правила проверок»)"
                )


def pytest_sessionfinish(session, exitstatus):
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if reporter is None:
        return
    banned = {k: len(reporter.stats.get(k, [])) for k in BANNED_OUTCOMES}
    if any(banned.values()):
        reporter.write_line(
            f"Пропущенные/xfail тесты запрещены политикой проекта: {banned}",
            red=True,
        )
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
