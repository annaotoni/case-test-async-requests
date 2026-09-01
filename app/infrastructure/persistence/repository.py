from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.domain.entities import Request
from app.domain.enums import RequestStatus
from app.infrastructure.persistence.models import RequestModel


class SQLAlchemyRequestRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, request: Request) -> Request:
        model = RequestModel(
            id=str(request.id),
            customer_id=request.customer_id,
            value=request.value,
            status=request.status.value,
            created_at=request.created_at,
            updated_at=request.updated_at,
        )
        self._session.add(model)
        self._session.commit()
        return request

    def get_by_id(self, request_id: UUID) -> Request | None:
        model = self._session.get(RequestModel, str(request_id))
        if model is None:
            return None
        return self._to_entity(model)

    def update_status(self, request_id: UUID, status: RequestStatus) -> None:
        self._session.execute(
            update(RequestModel)
            .where(RequestModel.id == str(request_id))
            .values(status=status.value, updated_at=datetime.now(UTC).replace(tzinfo=None))
        )
        self._session.commit()

    def _to_entity(self, model: RequestModel) -> Request:
        return Request(
            id=UUID(model.id),
            customer_id=model.customer_id,
            value=Decimal(str(model.value)),
            status=RequestStatus(model.status),
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
