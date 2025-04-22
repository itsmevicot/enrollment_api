from typing import List, Optional
import pika
from pika.exceptions import AMQPConnectionError
from pymongo.errors import DuplicateKeyError
from fastapi import HTTPException, status

from app.repositories.enrollment_repo import EnrollmentRepository
from app.schemas.enrollment_schema import EnrollmentCreate, EnrollmentRead
from app.enums.enrollment_status import EnrollmentStatus
from app.queue.provider import RabbitMQProvider
from app.config.settings import get_settings

settings = get_settings()

class EnrollmentService:
    def __init__(self, repo: EnrollmentRepository):
        self.repo = repo

    def create(self, payload: EnrollmentCreate, owner: str) -> EnrollmentRead:
        if self.repo.count_by_cpf_and_status(
            payload.cpf,
            [EnrollmentStatus.pending.value, EnrollmentStatus.approved.value],
            owner
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An enrollment is already pending or approved for this CPF"
            )

        if self.repo.count_by_cpf_and_status(
            payload.cpf,
            [EnrollmentStatus.rejected.value],
            owner
        ) >= 3:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Too many rejections; you cannot request again"
            )

        try:
            enrollment = self.repo.create(payload, owner)
        except DuplicateKeyError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An enrollment is already pending or approved for this CPF"
            )

        try:
            channel = RabbitMQProvider.get_channel()
        except AMQPConnectionError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Cannot connect to RabbitMQ",
            )

        channel.basic_publish(
            exchange="",
            routing_key=settings.rabbit_queue_name,
            body=enrollment.id.encode("utf-8"),
            properties=pika.BasicProperties(delivery_mode=2),
        )
        return enrollment

    def list(self, owner: str) -> List[EnrollmentRead]:
        return self.repo.list(owner)

    def get(self, id: str, owner: str) -> Optional[EnrollmentRead]:
        return self.repo.get(id, owner)

    def delete(self, id: str, owner: str) -> bool:
        return self.repo.delete(id, owner)
