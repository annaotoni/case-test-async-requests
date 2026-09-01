from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration

from app import composition
from app.application.use_cases.create_request import CreateRequestUseCase
from app.application.use_cases.get_request import GetRequestUseCase
from app.infrastructure.http.rate_limit import check_rate_limit
from app.infrastructure.persistence.repository import SQLAlchemyRequestRepository
from app.main import app
from tests.fakes import FakeCache


@pytest.fixture
def client(sqlite_session):
    fake_publisher = MagicMock()
    fake_cache = FakeCache()

    def override_create():
        repo = SQLAlchemyRequestRepository(sqlite_session)
        yield CreateRequestUseCase(repo, fake_publisher, topic="requests.created")

    def override_get():
        repo = SQLAlchemyRequestRepository(sqlite_session)
        yield GetRequestUseCase(repo, fake_cache, cache_ttl=60)

    app.dependency_overrides[composition.get_create_use_case] = override_create
    app.dependency_overrides[composition.get_get_use_case] = override_get
    app.dependency_overrides[check_rate_limit] = lambda: None

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

    app.dependency_overrides.clear()


def test_create_returns_201_with_pending(client):
    response = client.post("/requests", json={"customer_id": "99", "value": 500.0})
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "PENDING"
    assert data["customer_id"] == "99"
    assert "id" in data


def test_get_existing_request(client):
    create = client.post("/requests", json={"customer_id": "99", "value": 500.0})
    request_id = create.json()["id"]
    response = client.get(f"/requests/{request_id}")
    assert response.status_code == 200
    assert response.json()["id"] == request_id


def test_get_nonexistent_returns_404(client):
    response = client.get(f"/requests/{uuid4()}")
    assert response.status_code == 404
    assert "detail" in response.json()


def test_create_invalid_value_returns_422(client):
    response = client.post("/requests", json={"customer_id": "99", "value": -10.0})
    assert response.status_code == 422


def test_create_empty_customer_id_returns_422(client):
    response = client.post("/requests", json={"customer_id": "  ", "value": 100.0})
    assert response.status_code == 422
