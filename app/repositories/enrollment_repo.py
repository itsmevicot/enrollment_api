from datetime import datetime, timezone
from typing import List, Optional
from bson import ObjectId, errors as bson_errors
from pymongo.database import Database

from app.enums.enrollment_status import EnrollmentStatus
from app.schemas.enrollment_schema import EnrollmentRead, EnrollmentCreate
from app.utils.validators import normalize_cpf


class EnrollmentRepository:
    def __init__(self, db: Database):
        self.collection = db["enrollments"]

    def _doc_to_model(self, doc) -> EnrollmentRead:
        return EnrollmentRead.from_document(doc)

    def create(self, payload: EnrollmentCreate) -> EnrollmentRead:
        data = payload.model_dump()
        data["cpf"] = normalize_cpf(data["cpf"])
        data["status"] = EnrollmentStatus.pending.value
        data["rejection_reason"] = None
        data["created_at"] = datetime.now(timezone.utc)
        data["processed_at"] = None

        result = self.collection.insert_one(data)
        doc = {**data, "_id": result.inserted_id}
        return self._doc_to_model(doc)

    def get(self, id: str) -> Optional[EnrollmentRead]:
        try:
            oid = ObjectId(id)
        except (bson_errors.InvalidId, TypeError):
            return None
        doc = self.collection.find_one({"_id": oid})
        return doc and self._doc_to_model(doc)

    def delete(self, id: str) -> bool:
        try:
            oid = ObjectId(id)
        except (bson_errors.InvalidId, TypeError):
            return False
        res = self.collection.delete_one({"_id": oid})
        return res.deleted_count > 0

    def update_status(self, id: str, new_status: EnrollmentStatus) -> bool:
        try:
            oid = ObjectId(id)
        except (bson_errors.InvalidId, TypeError):
            return False
        res = self.collection.update_one(
            {"_id": oid},
            {"$set": {"status": new_status.value}}
        )
        return res.modified_count > 0

    def update_rejection(self, id: str, reason: str) -> None:
        try:
            oid = ObjectId(id)
        except (bson_errors.InvalidId, TypeError):
            return
        self.collection.update_one(
            {"_id": oid},
            {"$set": {
                "status": EnrollmentStatus.rejected.value,
                "rejection_reason": reason
            }}
        )

    def list(self) -> List[EnrollmentRead]:
        return [self._doc_to_model(doc) for doc in self.collection.find()]

    def count_by_cpf_and_status(self, cpf: str, statuses: List[str]) -> int:
        return self.collection.count_documents({
            "cpf": cpf,
            "status": {"$in": statuses}
        })
