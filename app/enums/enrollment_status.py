from enum import Enum


class EnrollmentStatus(str, Enum):
    pending   = "pending"
    approved  = "approved"
    rejected  = "rejected"
    failed    = "failed"
