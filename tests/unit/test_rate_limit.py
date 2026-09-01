import pytest
from unittest.mock import MagicMock, patch

pytestmark = pytest.mark.unit
from fastapi import HTTPException

from app.infrastructure.config import settings


def _make_request(host: str = "127.0.0.1"):
    request = MagicMock()
    request.client.host = host
    return request


def test_rate_limit_allows_within_window():
    mock_pipe = MagicMock()
    mock_pipe.execute.return_value = [1, True]

    mock_redis = MagicMock()
    mock_redis.pipeline.return_value = mock_pipe

    with patch("app.infrastructure.http.rate_limit._redis", mock_redis):
        from app.infrastructure.http.rate_limit import check_rate_limit
        check_rate_limit(_make_request())

    mock_pipe.incr.assert_called_once()
    mock_pipe.expire.assert_called_once_with(
        "rate_limit:127.0.0.1", settings.rate_limit_window
    )


def test_rate_limit_blocks_when_limit_exceeded():
    mock_pipe = MagicMock()
    mock_pipe.execute.return_value = [settings.rate_limit_requests + 1, True]

    mock_redis = MagicMock()
    mock_redis.pipeline.return_value = mock_pipe

    with patch("app.infrastructure.http.rate_limit._redis", mock_redis):
        from app.infrastructure.http.rate_limit import check_rate_limit
        with pytest.raises(HTTPException) as exc_info:
            check_rate_limit(_make_request())

    assert exc_info.value.status_code == 429


def test_rate_limit_always_sets_expire():
    """EXPIRE deve ser chamado sempre — mesmo quando count > 1."""
    mock_pipe = MagicMock()
    mock_pipe.execute.return_value = [5, True]

    mock_redis = MagicMock()
    mock_redis.pipeline.return_value = mock_pipe

    with patch("app.infrastructure.http.rate_limit._redis", mock_redis):
        from app.infrastructure.http.rate_limit import check_rate_limit
        check_rate_limit(_make_request())

    mock_pipe.expire.assert_called_once()


def test_rate_limit_uses_transaction_pipeline():
    """Pipeline deve ser criado com transaction=True para atomicidade."""
    mock_redis = MagicMock()
    mock_pipe = MagicMock()
    mock_pipe.execute.return_value = [1, True]
    mock_redis.pipeline.return_value = mock_pipe

    with patch("app.infrastructure.http.rate_limit._redis", mock_redis):
        from app.infrastructure.http.rate_limit import check_rate_limit
        check_rate_limit(_make_request())

    mock_redis.pipeline.assert_called_once_with(transaction=True)
