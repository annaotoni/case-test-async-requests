import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.infrastructure.http.middleware import CorrelationIdMiddleware
from app.infrastructure.http.router import router
from app.infrastructure.logging import configure_logging

configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="Processamento de Solicitações")

app.add_middleware(CorrelationIdMiddleware)
app.include_router(router)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Erro interno em %s: %s", request.url, exc)
    return JSONResponse(status_code=500, content={"detail": "Erro interno do servidor"})


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/health/ready")
def readiness() -> dict:
    from app import composition
    # Banco acessível e aceitando conexões.
    try:
        with composition.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(status_code=503, detail="database unavailable")
    # Cache acessível.
    try:
        composition.redis_client.ping()
    except Exception:
        raise HTTPException(status_code=503, detail="cache unavailable")
    return {"status": "ready"}
