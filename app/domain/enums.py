from enum import Enum


class RequestStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    FAILED = "FAILED"
