import json
import logging
import time
from uuid import UUID

import redis
from kafka import KafkaConsumer, KafkaProducer
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.domain.enums import RequestStatus
from app.infrastructure.cache.redis_cache import RedisCache
from app.infrastructure.config import settings
from app.infrastructure.persistence.repository import SQLAlchemyRequestRepository
from app.application.use_cases.process_request import ProcessRequestUseCase

from app.infrastructure.logging import configure_logging, correlation_id_var
configure_logging()
logger = logging.getLogger(__name__)

MAX_RETRIES = 3
# Teto de backoff bem abaixo do max.poll.interval.ms (padrão Kafka: 300s).
MAX_BACKOFF_SECONDS = 30

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine)
redis_client = redis.from_url(settings.redis_url)


def _process(request_id: str) -> None:
    session = SessionLocal()
    try:
        repo = SQLAlchemyRequestRepository(session)
        cache = RedisCache(redis_client)
        ProcessRequestUseCase(repo, cache).execute(UUID(request_id))
    finally:
        session.close()


def _mark_failed(request_id: str) -> None:
    session = SessionLocal()
    try:
        repo = SQLAlchemyRequestRepository(session)
        repo.update_status(UUID(request_id), RequestStatus.FAILED)
    finally:
        session.close()


def run() -> None:
    consumer = KafkaConsumer(
        settings.kafka_topic,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=settings.kafka_group_id,
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        value_deserializer=lambda m: json.loads(m.decode()),
    )
    dlq_producer = KafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        value_serializer=lambda v: json.dumps(v).encode(),
    )

    logger.info("Consumer iniciado, aguardando mensagens em '%s'...", settings.kafka_topic)

    for message in consumer:
        payload = message.value
        request_id = payload.get("request_id")
        correlation_id_var.set(payload.get("correlation_id", ""))

        if not request_id:
            consumer.commit()
            continue

        success = False
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                _process(request_id)
                success = True
                logger.info("request_id=%s processado com sucesso", request_id)
                break
            except Exception as exc:
                logger.warning(
                    "Tentativa %d/%d falhou para request_id=%s: %s",
                    attempt, MAX_RETRIES, request_id, exc,
                )
                time.sleep(min(attempt, MAX_BACKOFF_SECONDS))

        if not success:
            logger.error("request_id=%s enviado para DLQ após %d tentativas", request_id, MAX_RETRIES)
            try:
                dlq_producer.send(settings.kafka_dlq_topic, value=payload)
                dlq_producer.flush()
                _mark_failed(request_id)
            except Exception as exc:
                # Offset não commitado: mensagem será reentregue. A guarda
                # de idempotência (status != PENDING) protege de duplo processamento.
                logger.error(
                    "Falha no caminho DLQ/FAILED para request_id=%s: %s. "
                    "Offset não commitado — mensagem será reprocessada.",
                    request_id, exc,
                )
                continue

        consumer.commit()


if __name__ == "__main__":
    run()
