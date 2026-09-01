from decimal import Decimal

from app.application.ports import EventPublisher, RequestRepository
from app.domain.entities import Request


class CreateRequestUseCase:
    def __init__(self, repo: RequestRepository, publisher: EventPublisher, topic: str) -> None:
        self._repo = repo
        self._publisher = publisher
        self._topic = topic

    def execute(self, customer_id: str, value: Decimal, correlation_id: str = "") -> Request:
        request = Request(customer_id=customer_id, value=value)
        self._repo.save(request)
        self._publisher.publish(
            topic=self._topic,
            key=str(request.id),
            payload={
                "request_id": str(request.id),
                "correlation_id": correlation_id,
            },
        )
        return request
