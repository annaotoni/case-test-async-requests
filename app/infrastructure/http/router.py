from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.composition import get_create_use_case, get_get_use_case
from app.domain.entities import Request
from app.infrastructure.http.rate_limit import check_rate_limit
from app.infrastructure.http.schemas import CreateRequestSchema, RequestResponseSchema
from app.infrastructure.logging import correlation_id_var

router = APIRouter(prefix="/requests", tags=["requests"])


def _to_response(request: Request) -> RequestResponseSchema:
    return RequestResponseSchema(
        id=str(request.id),
        customer_id=request.customer_id,
        value=request.value,
        status=request.status.value,
    )


@router.post(
    "/",
    status_code=201,
    response_model=RequestResponseSchema,
    dependencies=[Depends(check_rate_limit)],
)
def create_request(body: CreateRequestSchema, uc=Depends(get_create_use_case)):
    request = uc.execute(body.customer_id, body.value, correlation_id_var.get(""))
    return _to_response(request)


@router.get("/{request_id}", response_model=RequestResponseSchema)
def get_request(request_id: UUID, uc=Depends(get_get_use_case)):
    request = uc.execute(request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada")
    return _to_response(request)
