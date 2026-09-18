import pytest
from fastapi.testclient import TestClient
from app.config import get_settings
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def api_version():
    return get_settings().app_version
