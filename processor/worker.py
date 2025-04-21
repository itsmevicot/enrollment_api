import time
from typing import List, Dict

import httpx
from bson import ObjectId

from app.clients.age_groups_client import AgeGroupsClient
from app.config.settings import get_settings
from app.database.provider import DatabaseProvider
from app.enums.enrollment_status import EnrollmentStatus
from app.queue.provider import RabbitMQProvider


settings = get_settings()
db = DatabaseProvider.get_db()
col = db["enrollments"]

_http = httpx.Client(base_url=settings.age_groups_api_url.rstrip("/"))
_age_client = AgeGroupsClient(settings.age_groups_api_url, _http)

def fetch_age_groups_with_retry(max_attempts: int = 5) -> List[Dict]:
    """
    Try up to `max_attempts` to fetch /age-groups/,
    backing off by +3s, +6s, +9s, ... after each failure.
    """
    delay = 0
    for attempt in range(1, max_attempts + 1):
        try:
            return _age_client.list()
        except Exception:
            if attempt == max_attempts:
                raise
            delay += 3 * attempt
            time.sleep(delay)

def process_one(ch, method, props, body):
    enrollment_id = body.decode()
    doc = col.find_one({"_id": ObjectId(enrollment_id)})
    if not doc:
        return ch.basic_ack(delivery_tag=method.delivery_tag)

    time.sleep(2)

    try:
        groups = fetch_age_groups_with_retry()
    except Exception:
        col.update_one(
            {"_id": ObjectId(enrollment_id)},
            {"$set": {"status": EnrollmentStatus.failed.value}}
        )
        return ch.basic_ack(delivery_tag=method.delivery_tag)

    age = doc["age"]
    cpf = doc["cpf"]

    if not any(g["min_age"] <= age <= g["max_age"] for g in groups):
        ranges = ", ".join(f"{g['min_age']}–{g['max_age']}" for g in groups)
        reason = f"Age {age} not in any group ({ranges})"
        col.update_one(
            {"_id": ObjectId(enrollment_id)},
            {"$set": {
                "status": EnrollmentStatus.rejected.value,
                "rejection_reason": reason
            }}
        )
        return ch.basic_ack(delivery_tag=method.delivery_tag)

    if col.count_documents({
            "cpf": cpf,
            "status": EnrollmentStatus.approved.value
        }) > 0:
        reason = "An enrollment is already approved for this CPF"
        col.update_one(
            {"_id": ObjectId(enrollment_id)},
            {"$set": {
                "status": EnrollmentStatus.rejected.value,
                "rejection_reason": reason
            }}
        )
        return ch.basic_ack(delivery_tag=method.delivery_tag)

    col.update_one(
        {"_id": ObjectId(enrollment_id)},
        {"$set": {"status": EnrollmentStatus.approved.value}}
    )
    return ch.basic_ack(delivery_tag=method.delivery_tag)

def main():
    ch = RabbitMQProvider.get_channel()
    ch.basic_qos(prefetch_count=1)
    ch.basic_consume(
        queue=settings.rabbit_queue_name,
        on_message_callback=process_one
    )
    print(" [*] Waiting for enrollment messages. To exit press CTRL+C")
    ch.start_consuming()

if __name__ == "__main__":
    main()
