from decimal import Decimal

import pytest

from app.domain.enums import RequestStatus

pytestmark = pytest.mark.unit
from app.domain.services import decide_status


@pytest.mark.parametrize("value,expected", [
    (Decimal("0.01"), RequestStatus.APPROVED),
    (Decimal("999.99"), RequestStatus.APPROVED),
    (Decimal("1000"), RequestStatus.APPROVED),
    (Decimal("1000.01"), RequestStatus.MANUAL_REVIEW),
    (Decimal("9999.99"), RequestStatus.MANUAL_REVIEW),
])
def test_decide_status(value: Decimal, expected: RequestStatus) -> None:
    assert decide_status(value) == expected
