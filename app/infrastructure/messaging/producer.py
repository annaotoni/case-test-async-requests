import json
import logging

from kafka import KafkaProducer

logger = logging.getLogger(__name__)


class KafkaEventPublisher:
    def __init__(self, bootstrap_servers: str) -> None:
        self._bootstrap_servers = bootstrap_servers
        self._producer: KafkaProducer | None = None

    def _get_producer(self) -> KafkaProducer:
        if self._producer is None:
            self._producer = KafkaProducer(
                bootstrap_servers=self._bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode(),
                key_serializer=lambda k: k.encode() if k else None,
                retries=3,
            )
        return self._producer

    def publish(self, topic: str, key: str, payload: dict) -> None:
        try:
            self._get_producer().send(topic, key=key, value=payload).get(timeout=10)
        except Exception as exc:
            logger.error("Falha ao publicar no Kafka topic=%s key=%s: %s", topic, key, exc)
            raise
