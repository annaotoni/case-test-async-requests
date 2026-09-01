import pytest
from decimal import Decimal
from uuid import uuid4

from app.domain.entities import Request
from app.domain.enums import RequestStatus

pytestmark = pytest.mark.integration
from app.infrastructure.persistence.repository import SQLAlchemyRequestRepository


def test_save_and_get(sqlite_session):
    repo = SQLAlchemyRequestRepository(sqlite_session)
    req = Request(customer_id="42", value=Decimal("750"))
    repo.save(req)
    found = repo.get_by_id(req.id)
    assert found is not None
    assert found.customer_id == "42"
    assert found.value == Decimal("750")
    assert found.status == RequestStatus.PENDING


def test_update_status(sqlite_session):
    repo = SQLAlchemyRequestRepository(sqlite_session)
    req = Request(customer_id="42", value=Decimal("750"))
    repo.save(req)
    repo.update_status(req.id, RequestStatus.APPROVED)
    found = repo.get_by_id(req.id)
    assert found.status == RequestStatus.APPROVED


def test_get_nonexistent_returns_none(sqlite_session):
    repo = SQLAlchemyRequestRepository(sqlite_session)
    assert repo.get_by_id(uuid4()) is None
