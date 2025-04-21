from typing import List, Optional

import pika

from app.repositories.enrollment_repo import EnrollmentRepository
from app.schemas.enrollment_schema import EnrollmentCreate, EnrollmentRead
from app.enums.enrollment_status import EnrollmentStatus
from app.queue.provider import RabbitMQProvider
from app.config.settings import get_settings

settings = get_settings()

class EnrollmentService:
    """
    - Applies pre‑persist business rules (no duplicate pending/approved;
      no more than 3 prior rejections).
    - Persists the enrollment as `status = pending`.
    - Publishes its ID to RabbitMQ for asynchronous processing.
    """
    def __init__(
        self,
        repo: EnrollmentRepository,
    ):
        self.repo = repo
        self._channel = RabbitMQProvider.get_channel()

    def list(self) -> List[EnrollmentRead]:
        return self.repo.list()

    def get(self, id: str) -> Optional[EnrollmentRead]:
        return self.repo.get(id)

    def create(self, payload: EnrollmentCreate) -> EnrollmentRead:
        if self.repo.count_by_cpf_and_status(
            payload.cpf,
            [EnrollmentStatus.pending.value, EnrollmentStatus.approved.value],
        ):
            raise ValueError("An enrollment is already pending or approved for this CPF")

        if self.repo.count_by_cpf_and_status(
            payload.cpf,
            [EnrollmentStatus.rejected.value],
        ) >= 3:
            raise ValueError("Too many rejections; you cannot request again")

        enrollment = self.repo.create(payload)

        self._channel.basic_publish(
            exchange="",
            routing_key=settings.rabbit_queue_name,
            body=enrollment.id.encode("utf-8"),
            properties=pika.BasicProperties(delivery_mode=2),
        )

        return enrollment

    def delete(self, id: str) -> bool:
        return self.repo.delete(id)
