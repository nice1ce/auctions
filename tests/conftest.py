import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.db import Base, get_db

# Используем основную БД, но с транзакционной изоляцией для каждого теста
TEST_DATABASE_URL = "postgresql+psycopg://auction:auction@localhost:5432/auction_db"


@pytest.fixture(scope="session")
def test_engine():
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(test_engine):
    connection = test_engine.connect()
    transaction = connection.begin()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=connection)
    session = SessionLocal()

    def override_get_db():
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    yield session

    # Гарантированный откат всех изменений после каждого теста
    transaction.rollback()
    connection.close()
    app.dependency_overrides.clear()


@pytest.fixture
def client(db_session):
    return TestClient(app)
