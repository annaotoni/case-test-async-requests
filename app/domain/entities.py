from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from app.domain.enums import RequestStatus


@dataclass
class Request:
    customer_id: str
    value: Decimal
    id: UUID = field(default_factory=uuid4)
    status: RequestStatus = RequestStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC).replace(tzinfo=None))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC).replace(tzinfo=None))
