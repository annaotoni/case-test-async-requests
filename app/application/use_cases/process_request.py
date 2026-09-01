from uuid import UUID

from app.application.ports import CachePort, RequestRepository
from app.domain.entities import Request
from app.domain.enums import RequestStatus
from app.domain.services import decide_status
from app.infrastructure.cache.keys import request_cache_key


class ProcessRequestUseCase:
    def __init__(self, repo: RequestRepository, cache: CachePort) -> None:
        self._repo = repo
        self._cache = cache

    def execute(self, request_id: UUID) -> Request | None:
        request = self._repo.get_by_id(request_id)

        # Idempotência: reprocessar solicitação já finalizada é no-op seguro.
        if request is None or request.status != RequestStatus.PENDING:
            return request

        new_status = decide_status(request.value)
        self._repo.update_status(request_id, new_status)
        self._cache.delete(request_cache_key(request_id))
        request.status = new_status
        return request
