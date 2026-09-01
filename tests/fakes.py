from app.domain.entities import Request
from app.domain.enums import RequestStatus


class FakeRepo:
    def __init__(self) -> None:
        self._store: dict = {}

    def save(self, request: Request) -> Request:
        self._store[request.id] = request
        return request

    def get_by_id(self, request_id):
        return self._store.get(request_id)

    def update_status(self, request_id, status):
        if request_id in self._store:
            self._store[request_id].status = status


class FakePublisher:
    def __init__(self) -> None:
        self.messages: list = []

    def publish(self, topic, key, payload):
        self.messages.append({"topic": topic, "key": key, "payload": payload})


class FakeCache:
    def __init__(self) -> None:
        self._store: dict = {}

    def get(self, key):
        return self._store.get(key)

    def set(self, key, value, ttl):
        self._store[key] = value

    def delete(self, key):
        self._store.pop(key, None)
