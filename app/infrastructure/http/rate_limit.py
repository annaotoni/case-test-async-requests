import redis as redis_lib
from fastapi import HTTPException, Request

from app.infrastructure.config import settings

_redis = redis_lib.from_url(settings.redis_url)


# Proteção contra abuso do endpoint de criação por IP de origem.
def check_rate_limit(request: Request) -> None:
    client_ip = request.client.host if request.client else "unknown"
    key = f"rate_limit:{client_ip}"

    # Pipeline transacional garante que INCR e EXPIRE são executados
    # atomicamente — elimina race entre os dois comandos.
    pipe = _redis.pipeline(transaction=True)
    pipe.incr(key)
    pipe.expire(key, settings.rate_limit_window)
    count, _ = pipe.execute()

    if count > settings.rate_limit_requests:
        raise HTTPException(
            status_code=429,
            detail="Limite de requisições excedido. Tente novamente em instantes.",
        )
