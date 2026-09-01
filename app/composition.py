import redis
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.application.use_cases.create_request import CreateRequestUseCase
from app.application.use_cases.get_request import GetRequestUseCase
from app.infrastructure.cache.redis_cache import RedisCache
from app.infrastructure.config import settings
from app.infrastructure.messaging.producer import KafkaEventPublisher
from app.infrastructure.persistence.repository import SQLAlchemyRequestRepository

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(engine)
redis_client = redis.from_url(settings.redis_url)

_publisher: KafkaEventPublisher | None = None


def _get_publisher() -> KafkaEventPublisher:
    global _publisher
    if _publisher is None:
        _publisher = KafkaEventPublisher(settings.kafka_bootstrap_servers)
    return _publisher


def get_create_use_case():
    session = SessionLocal()
    try:
        repo = SQLAlchemyRequestRepository(session)
        yield CreateRequestUseCase(repo, _get_publisher(), settings.kafka_topic)
    finally:
        session.close()


def get_get_use_case():
    session = SessionLocal()
    try:
        repo = SQLAlchemyRequestRepository(session)
        cache = RedisCache(redis_client)
        yield GetRequestUseCase(repo, cache, settings.cache_ttl)
    finally:
        session.close()
