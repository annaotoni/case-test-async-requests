import pytest
from decimal import Decimal
from uuid import uuid4

pytestmark = pytest.mark.unit

from app.application.use_cases.create_request import CreateRequestUseCase
from app.application.use_cases.get_request import GetRequestUseCase
from app.application.use_cases.process_request import ProcessRequestUseCase
from app.domain.entities import Request
from app.domain.enums import RequestStatus
from app.infrastructure.cache.keys import request_cache_key
from tests.fakes import FakeCache, FakePublisher, FakeRepo


def test_create_stores_pending_and_publishes():
    repo, publisher = FakeRepo(), FakePublisher()
    uc = CreateRequestUseCase(repo, publisher, topic="requests.created")
    req = uc.execute("123", Decimal("500"))
    assert req.status == RequestStatus.PENDING
    assert len(publisher.messages) == 1
    assert publisher.messages[0]["key"] == str(req.id)


def test_process_approved():
    repo, cache = FakeRepo(), FakeCache()
    req = Request(customer_id="1", value=Decimal("500"))
    repo.save(req)
    ProcessRequestUseCase(repo, cache).execute(req.id)
    assert repo.get_by_id(req.id).status == RequestStatus.APPROVED


def test_process_manual_review():
    repo, cache = FakeRepo(), FakeCache()
    req = Request(customer_id="1", value=Decimal("1500"))
    repo.save(req)
    ProcessRequestUseCase(repo, cache).execute(req.id)
    assert repo.get_by_id(req.id).status == RequestStatus.MANUAL_REVIEW


def test_process_boundary_exactly_1000():
    repo, cache = FakeRepo(), FakeCache()
    req = Request(customer_id="1", value=Decimal("1000"))
    repo.save(req)
    ProcessRequestUseCase(repo, cache).execute(req.id)
    assert repo.get_by_id(req.id).status == RequestStatus.APPROVED


def test_process_idempotent_skips_already_approved():
    repo, cache = FakeRepo(), FakeCache()
    req = Request(customer_id="1", value=Decimal("500"), status=RequestStatus.APPROVED)
    repo.save(req)
    ProcessRequestUseCase(repo, cache).execute(req.id)
    assert repo.get_by_id(req.id).status == RequestStatus.APPROVED


def test_process_invalidates_cache():
    repo, cache = FakeRepo(), FakeCache()
    req = Request(customer_id="1", value=Decimal("500"))
    repo.save(req)
    cache.set(request_cache_key(req.id), "stale_data", 300)
    ProcessRequestUseCase(repo, cache).execute(req.id)
    assert cache.get(f"request:{req.id}") is None


def test_process_nonexistent_returns_none():
    repo, cache = FakeRepo(), FakeCache()
    result = ProcessRequestUseCase(repo, cache).execute(uuid4())
    assert result is None


def test_get_cache_miss_then_hit():
    repo, cache = FakeRepo(), FakeCache()
    req = Request(customer_id="1", value=Decimal("500"))
    repo.save(req)
    uc = GetRequestUseCase(repo, cache, cache_ttl=60)
    result1 = uc.execute(req.id)
    assert result1 is not None
    assert cache.get(request_cache_key(req.id)) is not None
    result2 = uc.execute(req.id)
    assert result2.id == result1.id


def test_get_not_found_returns_none():
    repo, cache = FakeRepo(), FakeCache()
    assert GetRequestUseCase(repo, cache).execute(uuid4()) is None
