from uuid import UUID


def request_cache_key(request_id: UUID) -> str:
    return f"request:{request_id}"
