from decimal import Decimal

from app.domain.enums import RequestStatus


# Solicitações acima de R$ 1.000 exigem análise manual antes de aprovação.
def decide_status(value: Decimal) -> RequestStatus:
    if value <= Decimal("1000"):
        return RequestStatus.APPROVED
    return RequestStatus.MANUAL_REVIEW
