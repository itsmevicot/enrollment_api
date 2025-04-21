from enum import Enum


class EnrollmentStatus(str, Enum):
    pending   = "pending"
    retrying = "retrying"
    approved  = "approved"
    rejected  = "rejected"
    failed    = "failed"
