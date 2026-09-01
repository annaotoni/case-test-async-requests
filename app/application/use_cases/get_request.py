import json
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from app.application.ports import CachePort, RequestRepository
from app.domain.entities import Request
from app.domain.enums import RequestStatus
from app.infrastructure.cache.keys import request_cache_key


class GetRequestUseCase:
    def __init__(self, repo: RequestRepository, cache: CachePort, cache_ttl: int = 900) -> None:
        self._repo = repo
        self._cache = cache
        self._ttl = cache_ttl

    def execute(self, request_id: UUID) -> Request | None:
        key = request_cache_key(request_id)
        cached = self._cache.get(key)
        if cached:
            return self._deserialize(cached)

        request = self._repo.get_by_id(request_id)
        if request is None:
            return None

        self._cache.set(key, self._serialize(request), ttl=self._ttl)
        return request

    def _serialize(self, request: Request) -> str:
        return json.dumps({
            "id": str(request.id),
            "customer_id": request.customer_id,
            "value": str(request.value),
            "status": request.status.value,
            "created_at": request.created_at.isoformat(),
            "updated_at": request.updated_at.isoformat(),
        })

    def _deserialize(self, data: str) -> Request:
        d = json.loads(data)
        return Request(
            id=UUID(d["id"]),
            customer_id=d["customer_id"],
            value=Decimal(d["value"]),
            status=RequestStatus(d["status"]),
            created_at=datetime.fromisoformat(d["created_at"]),
            updated_at=datetime.fromisoformat(d["updated_at"]),
        )
