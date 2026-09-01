import redis as redis_lib


class RedisCache:
    def __init__(self, client: redis_lib.Redis) -> None:
        self._client = client

    def get(self, key: str) -> str | None:
        value = self._client.get(key)
        return value.decode() if value else None

    def set(self, key: str, value: str, ttl: int) -> None:
        self._client.setex(key, ttl, value)

    def delete(self, key: str) -> None:
        self._client.delete(key)
