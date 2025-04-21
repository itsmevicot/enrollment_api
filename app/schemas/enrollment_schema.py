from pydantic import BaseModel, Field, field_validator, ConfigDict

from app.enums.enrollment_status import EnrollmentStatus
from app.utils.validators import normalize_cpf, is_valid_cpf

class EnrollmentCreate(BaseModel):
    name: str
    cpf: str
    age: int

    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator("cpf", mode="before")
    def strip_fmt(cls, v):
        return normalize_cpf(v)

    @field_validator("cpf")
    def check_cpf(cls, v):
        if not is_valid_cpf(v):
            raise ValueError("Invalid CPF")
        return v

class EnrollmentRead(EnrollmentCreate):
    id: str = Field(..., description="MongoDB ObjectId as string")
    status: EnrollmentStatus = Field(
        EnrollmentStatus.pending, description="Processing status"
    )
    rejection_reason: str | None = Field(
        None,
        description="Reason for rejection, if applicable",
    )

    model_config = ConfigDict(from_attributes=True, validate_by_name=True)

    @classmethod
    def from_document(cls, doc: dict) -> "EnrollmentRead":
        """
        Build without re‑running all validators.
        """
        return cls.model_construct(
            id=str(doc["_id"]),
            name=doc["name"],
            cpf=doc["cpf"],
            age=doc["age"],
            status=EnrollmentStatus(doc["status"]),
            rejection_reason=doc.get("rejection_reason"),
        )