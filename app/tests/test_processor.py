from datetime import datetime, timezone

import pytest
from bson import ObjectId

import processor.worker as worker_module
from app.database.provider import DatabaseProvider
from app.enums.enrollment_status import EnrollmentStatus


def insert_enrollment(cpf, age, status=EnrollmentStatus.pending.value):
    """Helper to inject a doc into Mongo and return its ID."""
    db = DatabaseProvider.get_db()
    now = datetime.now(timezone.utc)
    data = {
        "name": "TestUser",
        "cpf": cpf,
        "age": age,
        "status": status,
        "rejection_reason": None,
        "created_at": now,
        "processed_at": None,
    }
    result = db["enrollments"].insert_one(data)
    return str(result.inserted_id)


class StubGroups:
    """Stub for fetch_age_groups_with_retry."""
    def __init__(self, groups, fail=False):
        self.groups = groups
        self.fail = fail

    def __call__(self, *args, **kwargs):
        if self.fail:
            raise Exception("upstream failure")
        return self.groups


def test_successful_approval(monkeypatch, dummy_channel, dummy_method):
    eid = insert_enrollment("11111111111", age=12)
    monkeypatch.setattr(worker_module, "fetch_age_groups_with_retry",
                        StubGroups([{"min_age":0,"max_age":20}]))
    worker_module.process_one(dummy_channel, dummy_method, None, eid.encode())
    doc = DatabaseProvider.get_db()["enrollments"].find_one({"_id": ObjectId(eid)})
    assert doc["status"] == EnrollmentStatus.approved.value
    assert dummy_channel.acked == [dummy_method.delivery_tag]
    assert dummy_channel.nacked == []


def test_business_reject_age_out(monkeypatch, dummy_channel, dummy_method):
    eid = insert_enrollment("22222222222", age=30)
    monkeypatch.setattr(worker_module, "fetch_age_groups_with_retry",
                        StubGroups([{"min_age":0,"max_age":20}]))
    worker_module.process_one(dummy_channel, dummy_method, None, eid.encode())
    doc = DatabaseProvider.get_db()["enrollments"].find_one({"_id": ObjectId(eid)})
    assert doc["status"] == EnrollmentStatus.rejected.value
    assert "Age 30 not in any group" in doc["rejection_reason"]
    assert dummy_channel.acked == [dummy_method.delivery_tag]


def test_business_reject_duplicate_approved(monkeypatch, dummy_channel, dummy_method):
    db = DatabaseProvider.get_db()
    eid1 = insert_enrollment("33333333333", age=5)
    db["enrollments"].update_one(
        {"_id": ObjectId(eid1)},
        {"$set": {"status": EnrollmentStatus.approved.value}}
    )
    eid2 = insert_enrollment("33333333333", age=4)
    monkeypatch.setattr(worker_module, "fetch_age_groups_with_retry",
                        StubGroups([{"min_age":0,"max_age":20}]))
    worker_module.process_one(dummy_channel, dummy_method, None, eid2.encode())
    doc2 = db["enrollments"].find_one({"_id": ObjectId(eid2)})
    assert doc2["status"] == EnrollmentStatus.rejected.value
    assert "already approved" in doc2["rejection_reason"]
    assert dummy_channel.acked == [dummy_method.delivery_tag]


def test_transient_failure_nack(monkeypatch, dummy_channel, dummy_method):
    eid = insert_enrollment("44444444444", age=3)
    monkeypatch.setattr(worker_module, "fetch_age_groups_with_retry",
                        StubGroups([], fail=True))
    worker_module.process_one(dummy_channel, dummy_method, None, eid.encode())
    doc = DatabaseProvider.get_db()["enrollments"].find_one({"_id": ObjectId(eid)})
    assert doc["status"] == EnrollmentStatus.failed.value
    assert doc["processed_at"] is not None
    assert dummy_channel.nacked == [(dummy_method.delivery_tag, False)]
    assert dummy_channel.acked == []


def test_missing_document_ack(dummy_channel, dummy_method):
    fake_id = "000000000000000000000000"
    worker_module.process_one(dummy_channel, dummy_method, None, fake_id.encode())
    assert dummy_channel.acked == [dummy_method.delivery_tag]
    assert dummy_channel.nacked == []


@pytest.mark.parametrize("prior_rejects, should_block", [
    (3, True),
    (2, False),
])
def test_rejection_limit(monkeypatch, dummy_channel, dummy_method, prior_rejects, should_block):
    for _ in range(prior_rejects):
        eid = insert_enrollment("55555555555", age=2)
        DatabaseProvider.get_db()["enrollments"].update_one(
            {"_id": ObjectId(eid)},
            {"$set": {"status": EnrollmentStatus.rejected.value}}
        )
    eid_new = insert_enrollment("55555555555", age=2)
    monkeypatch.setattr(worker_module, "fetch_age_groups_with_retry",
                        StubGroups([{"min_age":0,"max_age":10}]))
    worker_module.process_one(dummy_channel, dummy_method, None, eid_new.encode())
    doc_new = DatabaseProvider.get_db()["enrollments"].find_one({"_id": ObjectId(eid_new)})
    if should_block:
        assert doc_new["status"] == EnrollmentStatus.rejected.value
        assert "Too many rejections" in doc_new["rejection_reason"]
        assert dummy_channel.acked == [dummy_method.delivery_tag]
    else:
        assert doc_new["status"] == EnrollmentStatus.approved.value
        assert dummy_channel.acked == [dummy_method.delivery_tag]
