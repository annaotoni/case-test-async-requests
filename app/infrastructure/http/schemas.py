from decimal import Decimal

from pydantic import BaseModel, field_validator


class CreateRequestSchema(BaseModel):
    customer_id: str
    value: Decimal

    @field_validator("value")
    @classmethod
    def value_must_be_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("value deve ser maior que zero")
        return v

    @field_validator("customer_id")
    @classmethod
    def customer_id_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("customer_id não pode ser vazio")
        return v.strip()


class RequestResponseSchema(BaseModel):
    id: str
    customer_id: str
    value: Decimal
    status: str
