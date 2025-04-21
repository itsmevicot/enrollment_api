import time

import httpx
from bson import ObjectId

from app.config.settings import get_settings
from app.database.provider import DatabaseProvider
from app.enums.enrollment_status import EnrollmentStatus
from app.queue.provider import RabbitMQProvider

settings = get_settings()
db = DatabaseProvider.get_db()
client = httpx.Client(base_url=settings.age_groups_api_url.rstrip("/"))


def process_one(ch, method, props, body):
    enrollment_id = body.decode()
    col = db["enrollments"]
    doc = col.find_one({"_id": ObjectId(enrollment_id)})
    if not doc:
        return ch.basic_ack(delivery_tag=method.delivery_tag)

    time.sleep(2)

    resp = client.get("/age-groups/")
    resp.raise_for_status()
    groups = resp.json()

    age = doc["age"]
    cpf = doc["cpf"]

    in_group = any(g["min_age"] <= age <= g["max_age"] for g in groups)
    if not in_group:
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

    if col.count_documents({"cpf": cpf, "status": EnrollmentStatus.approved.value}) > 0:
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
