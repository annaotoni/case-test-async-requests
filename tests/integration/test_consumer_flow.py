from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

pytestmark = pytest.mark.integration

from app.domain.entities import Request
from app.domain.enums import RequestStatus
from app.infrastructure.persistence.repository import SQLAlchemyRequestRepository
from tests.fakes import FakeCache


def _fake_message(request_id: str) -> MagicMock:
    msg = MagicMock()
    msg.value = {"request_id": request_id}
    return msg


def _make_consumer(messages: list) -> MagicMock:
    mock = MagicMock()
    mock.__iter__ = MagicMock(return_value=iter(messages))
    return mock


def test_happy_path_approves_and_commits(sqlite_session):
    """Fluxo feliz: PENDING → APPROVED no banco, offset commitado."""
    repo = SQLAlchemyRequestRepository(sqlite_session)
    req = Request(customer_id="1", value=Decimal("500"))
    repo.save(req)

    mock_consumer = _make_consumer([_fake_message(str(req.id))])
    mock_dlq = MagicMock()

    with patch("consumer.SessionLocal", return_value=sqlite_session), \
         patch("consumer.RedisCache", return_value=FakeCache()), \
         patch("consumer.redis.from_url"), \
         patch("consumer.KafkaConsumer", return_value=mock_consumer), \
         patch("consumer.KafkaProducer", return_value=mock_dlq), \
         patch("consumer.time.sleep"):
        from consumer import run
        run()

    updated = repo.get_by_id(req.id)
    assert updated.status == RequestStatus.APPROVED
    mock_consumer.commit.assert_called_once()
    mock_dlq.send.assert_not_called()


def test_manual_review_path(sqlite_session):
    """value > 1000 → MANUAL_REVIEW no banco após processamento."""
    repo = SQLAlchemyRequestRepository(sqlite_session)
    req = Request(customer_id="2", value=Decimal("1500"))
    repo.save(req)

    mock_consumer = _make_consumer([_fake_message(str(req.id))])

    with patch("consumer.SessionLocal", return_value=sqlite_session), \
         patch("consumer.RedisCache", return_value=FakeCache()), \
         patch("consumer.redis.from_url"), \
         patch("consumer.KafkaConsumer", return_value=mock_consumer), \
         patch("consumer.KafkaProducer"), \
         patch("consumer.time.sleep"):
        from consumer import run
        run()

    updated = repo.get_by_id(req.id)
    assert updated.status == RequestStatus.MANUAL_REVIEW


def test_retry_exhaustion_marks_failed_in_db(sqlite_session):
    """Após 3 falhas de processamento: status FAILED no banco, DLQ enviado."""
    repo = SQLAlchemyRequestRepository(sqlite_session)
    req = Request(customer_id="3", value=Decimal("500"))
    repo.save(req)

    mock_consumer = _make_consumer([_fake_message(str(req.id))])
    mock_dlq = MagicMock()

    with patch("consumer.SessionLocal", return_value=sqlite_session), \
         patch("consumer.RedisCache", return_value=FakeCache()), \
         patch("consumer.redis.from_url"), \
         patch("consumer.KafkaConsumer", return_value=mock_consumer), \
         patch("consumer.KafkaProducer", return_value=mock_dlq), \
         patch("consumer._process", side_effect=RuntimeError("falha simulada")), \
         patch("consumer.time.sleep"):
        from consumer import run
        run()

    updated = repo.get_by_id(req.id)
    assert updated.status == RequestStatus.FAILED
    mock_dlq.send.assert_called_once()
    mock_dlq.flush.assert_called_once()
    mock_consumer.commit.assert_called_once()


def test_idempotency_already_approved_skips(sqlite_session):
    """Reprocessar solicitação APPROVED não altera status nem falha."""
    repo = SQLAlchemyRequestRepository(sqlite_session)
    req = Request(customer_id="4", value=Decimal("500"), status=RequestStatus.APPROVED)
    repo.save(req)

    mock_consumer = _make_consumer([_fake_message(str(req.id))])

    with patch("consumer.SessionLocal", return_value=sqlite_session), \
         patch("consumer.RedisCache", return_value=FakeCache()), \
         patch("consumer.redis.from_url"), \
         patch("consumer.KafkaConsumer", return_value=mock_consumer), \
         patch("consumer.KafkaProducer"), \
         patch("consumer.time.sleep"):
        from consumer import run
        run()

    updated = repo.get_by_id(req.id)
    assert updated.status == RequestStatus.APPROVED
    mock_consumer.commit.assert_called_once()


def test_offset_not_committed_when_mark_failed_raises(sqlite_session):
    """Se _mark_failed lançar exceção, offset NÃO é commitado."""
    mock_consumer = _make_consumer([_fake_message(str(uuid4()))])
    mock_dlq = MagicMock()

    with patch("consumer.SessionLocal"), \
         patch("consumer.redis.from_url"), \
         patch("consumer.KafkaConsumer", return_value=mock_consumer), \
         patch("consumer.KafkaProducer", return_value=mock_dlq), \
         patch("consumer._process", side_effect=RuntimeError("falha")), \
         patch("consumer._mark_failed", side_effect=RuntimeError("db error")), \
         patch("consumer.time.sleep"):
        from consumer import run
        run()

    mock_consumer.commit.assert_not_called()
