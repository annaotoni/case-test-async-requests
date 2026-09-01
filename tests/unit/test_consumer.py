import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4

pytestmark = pytest.mark.unit


def test_mark_failed_propagates_exception():
    """_mark_failed deve propagar exceções de banco — não engolir."""
    with patch("consumer.SessionLocal") as mock_sf:
        mock_session = MagicMock()
        mock_sf.return_value = mock_session
        with patch("consumer.SQLAlchemyRequestRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo_cls.return_value = mock_repo
            mock_repo.update_status.side_effect = RuntimeError("db offline")

            from consumer import _mark_failed
            with pytest.raises(RuntimeError, match="db offline"):
                _mark_failed(str(uuid4()))

    mock_session.close.assert_called_once()


def test_run_commits_offset_on_success():
    """Commit só ocorre após processamento bem-sucedido."""
    request_id = str(uuid4())
    fake_message = MagicMock()
    fake_message.value = {"request_id": request_id}

    mock_consumer = MagicMock()
    mock_consumer.__iter__ = MagicMock(return_value=iter([fake_message]))

    with patch("consumer.KafkaConsumer", return_value=mock_consumer), \
         patch("consumer.KafkaProducer"), \
         patch("consumer._process") as mock_process:
        from consumer import run
        run()

    mock_process.assert_called_once_with(request_id)
    mock_consumer.commit.assert_called_once()


def test_run_sends_dlq_and_marks_failed_after_retries():
    """Após MAX_RETRIES falhas, envia ao DLQ e marca FAILED antes do commit."""
    request_id = str(uuid4())
    fake_message = MagicMock()
    fake_message.value = {"request_id": request_id}

    mock_consumer = MagicMock()
    mock_consumer.__iter__ = MagicMock(return_value=iter([fake_message]))
    mock_dlq_producer = MagicMock()

    with patch("consumer.KafkaConsumer", return_value=mock_consumer), \
         patch("consumer.KafkaProducer", return_value=mock_dlq_producer), \
         patch("consumer._process", side_effect=RuntimeError("falha")), \
         patch("consumer._mark_failed") as mock_mark_failed, \
         patch("consumer.time.sleep"):
        from consumer import run
        run()

    mock_dlq_producer.send.assert_called_once()
    mock_dlq_producer.flush.assert_called_once()
    mock_mark_failed.assert_called_once_with(request_id)
    mock_consumer.commit.assert_called_once()


def test_run_does_not_commit_offset_when_mark_failed_raises():
    """Se _mark_failed falhar, offset NÃO deve ser commitado."""
    request_id = str(uuid4())
    fake_message = MagicMock()
    fake_message.value = {"request_id": request_id}

    mock_consumer = MagicMock()
    mock_consumer.__iter__ = MagicMock(return_value=iter([fake_message]))
    mock_dlq_producer = MagicMock()

    with patch("consumer.KafkaConsumer", return_value=mock_consumer), \
         patch("consumer.KafkaProducer", return_value=mock_dlq_producer), \
         patch("consumer._process", side_effect=RuntimeError("falha")), \
         patch("consumer._mark_failed", side_effect=RuntimeError("db error")), \
         patch("consumer.time.sleep"):
        from consumer import run
        run()

    mock_consumer.commit.assert_not_called()


def test_run_skips_message_without_request_id():
    """Mensagens sem request_id devem ser commitadas e ignoradas."""
    fake_message = MagicMock()
    fake_message.value = {}

    mock_consumer = MagicMock()
    mock_consumer.__iter__ = MagicMock(return_value=iter([fake_message]))

    with patch("consumer.KafkaConsumer", return_value=mock_consumer), \
         patch("consumer.KafkaProducer"), \
         patch("consumer._process") as mock_process:
        from consumer import run
        run()

    mock_process.assert_not_called()
    mock_consumer.commit.assert_called_once()
