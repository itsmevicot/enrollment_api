import logging
import time
from datetime import datetime, timezone
from typing import List, Dict

import httpx
from bson import ObjectId
from pika.adapters.blocking_connection import BlockingChannel

from app.clients.age_groups_client import AgeGroupsClient
from app.config.settings import get_settings
from app.database.provider import DatabaseProvider
from app.enums.enrollment_status import EnrollmentStatus
from app.queue.provider import RabbitMQProvider

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s"
)
logger = logging.getLogger("worker")

settings = get_settings()

_http = httpx.Client(
    base_url=settings.age_groups_api_url.rstrip("/"),
    auth=(settings.age_groups_api_username, settings.age_groups_api_password),
)
_age_client = AgeGroupsClient(settings.age_groups_api_url, _http)


def fetch_age_groups_with_retry(max_attempts: int = 5) -> List[Dict]:
    delay = 0
    for attempt in range(1, max_attempts + 1):
        try:
            logger.info(f"Fetching age groups (attempt {attempt})")
            return _age_client.list()
        except Exception:
            if attempt == max_attempts:
                logger.exception("Failed to fetch age groups after retries")
                raise
            delay += 3 * attempt
            time.sleep(delay)


def process_one(ch: BlockingChannel, method, props, body: bytes):
    col = DatabaseProvider.get_db()["enrollments"]
    enrollment_id = body.decode()
    logger.info(f"⏳ Received message for enrollment_id={enrollment_id!r}")

    doc = col.find_one({"_id": ObjectId(enrollment_id)})
    if not doc:
        logger.warning(f"No document found for {enrollment_id!r}; acking and skipping")
        return ch.basic_ack(delivery_tag=method.delivery_tag)

    time.sleep(2)

    try:
        groups = fetch_age_groups_with_retry()
    except Exception:
        logger.error(f"Marking enrollment {enrollment_id} as failed and NACKing")
        col.update_one(
            {"_id": ObjectId(enrollment_id)},
            {"$set": {
                "status": EnrollmentStatus.failed.value,
                "processed_at": datetime.now(timezone.utc)
            }}
        )
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        return

    age = doc.get("age")
    cpf = doc.get("cpf")

    rejected_count = col.count_documents({
        "cpf": cpf,
        "status": EnrollmentStatus.rejected.value
    })
    if rejected_count >= 3:
        reason = "Too many rejections; you cannot request again"
        logger.info(f"Rejecting {enrollment_id}: {reason}")
        col.update_one(
            {"_id": ObjectId(enrollment_id)},
            {"$set": {
                "status": EnrollmentStatus.rejected.value,
                "rejection_reason": reason,
                "processed_at": datetime.now(timezone.utc)
            }}
        )
        return ch.basic_ack(delivery_tag=method.delivery_tag)

    if not any(g["min_age"] <= age <= g["max_age"] for g in groups):
        reason = f"Age {age} not in any group"
        logger.info(f"Rejecting {enrollment_id}: {reason}")
        col.update_one(
            {"_id": ObjectId(enrollment_id)},
            {"$set": {
                "status": EnrollmentStatus.rejected.value,
                "rejection_reason": reason,
                "processed_at": datetime.now(timezone.utc)
            }}
        )
        return ch.basic_ack(delivery_tag=method.delivery_tag)

    if col.count_documents({
            "cpf": cpf,
            "status": EnrollmentStatus.approved.value
        }) > 0:
        reason = "An enrollment is already approved for this CPF"
        logger.info(f"Rejecting {enrollment_id}: {reason}")
        col.update_one(
            {"_id": ObjectId(enrollment_id)},
            {"$set": {
                "status": EnrollmentStatus.rejected.value,
                "rejection_reason": reason,
                "processed_at": datetime.now(timezone.utc)
            }}
        )
        return ch.basic_ack(delivery_tag=method.delivery_tag)

    logger.info(f"Approving enrollment {enrollment_id}")
    col.update_one(
        {"_id": ObjectId(enrollment_id)},
        {"$set": {
            "status": EnrollmentStatus.approved.value,
            "processed_at": datetime.now(timezone.utc)
        }}
    )
    return ch.basic_ack(delivery_tag=method.delivery_tag)


def main():
    logger.info("Worker starting up, connecting to RabbitMQ…")
    ch = RabbitMQProvider.get_channel()
    ch.basic_qos(prefetch_count=1)
    ch.basic_consume(
        queue=settings.rabbit_queue_name,
        on_message_callback=process_one
    )
    logger.info(f"[*] Waiting for messages on queue '{settings.rabbit_queue_name}'")
    ch.start_consuming()


if __name__ == "__main__":
    main()
