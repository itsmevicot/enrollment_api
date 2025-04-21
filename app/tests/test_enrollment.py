from fastapi import status

from app.database.provider import DatabaseProvider
from app.dependencies import get_age_groups_client
from app.enums.enrollment_status import EnrollmentStatus
from app.queue.provider import RabbitMQProvider
from app.repositories.enrollment_repo import EnrollmentRepository
from main import app


def test_health_success(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}

def test_health_mongo_down(client, monkeypatch):
    class BadDB:
        client = type("c", (), {
            "admin": type("a", (), {
                "command": staticmethod(lambda cmd: (_ for _ in ()).throw(Exception("fail")))
            })
        })
    monkeypatch.setattr(DatabaseProvider, "get_db", classmethod(lambda cls: BadDB()))
    r = client.get("/health/")
    assert r.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert "MongoDB" in r.json()["detail"]

def test_health_rabbit_down(client, monkeypatch):
    monkeypatch.setattr(RabbitMQProvider, "get_channel",
                        classmethod(lambda cls: (_ for _ in ()).throw(Exception("no rabbit"))))
    r = client.get("/health/")
    assert r.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert "RabbitMQ" in r.json()["detail"]

def test_create_fetch_delete_full_cycle(client):
    payload = {"name": "Alice", "cpf": "652.535.790-01", "age": 12}
    r = client.post("/enrollments/", json=payload)
    assert r.status_code == status.HTTP_201_CREATED
    body = r.json()

    assert body["name"]   == "Alice"
    assert body["cpf"] == "65253579001"
    assert body["age"]    == 12
    assert body["status"] == EnrollmentStatus.pending.value
    assert body["rejection_reason"] is None

    eid = body["id"]
    lst = client.get("/enrollments/").json()
    assert any(e["id"] == eid for e in lst)

    one = client.get(f"/enrollments/{eid}").json()
    assert one["id"] == eid

    d = client.delete(f"/enrollments/{eid}")
    assert d.status_code == status.HTTP_204_NO_CONTENT
    assert client.get(f"/enrollments/{eid}").status_code == status.HTTP_404_NOT_FOUND

def test_duplicate_pending_blocks(client):
    p = {"name": "Bob", "cpf": "953.740.110-30", "age": 2}
    r1 = client.post("/enrollments/", json=p)
    assert r1.status_code == status.HTTP_201_CREATED

    r2 = client.post("/enrollments/", json=p)
    assert r2.status_code == status.HTTP_400_BAD_REQUEST
    assert "already pending" in r2.json()["detail"]

def test_too_many_rejections_blocks(client):
    repo = EnrollmentRepository(DatabaseProvider.get_db())
    class DummyPayload:
        def model_dump(self):
            return {"name": "X", "cpf": "920.104.720-71", "age": 5}
    for _ in range(3):
        rec = repo.create(DummyPayload())
        repo.update_rejection(rec.id, "reason")
    r = client.post("/enrollments/", json={"name":"X","cpf":"920.104.720-71","age":5})
    assert r.status_code == status.HTTP_400_BAD_REQUEST
    assert "Too many rejections" in r.json()["detail"]

def test_invalid_cpf_422(client):
    r = client.post("/enrollments/", json={"name":"Z","cpf":"00000000000","age":5})
    assert r.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

def test_create_when_no_age_groups(client, age_groups_stub):
    empty = age_groups_stub
    empty._groups = []
    app.dependency_overrides[get_age_groups_client] = lambda: empty

    r = client.post("/enrollments/", json={"name":"NoGroups","cpf":"274.427.600-66","age":30})
    assert r.status_code == status.HTTP_201_CREATED

def test_duplicate_approved_blocks(client):
    repo = EnrollmentRepository(DatabaseProvider.get_db())

    class DummyPayload:
        def model_dump(self):
            return {"name": "Y", "cpf": "953.740.110-30", "age": 2}

    rec = repo.create(DummyPayload())
    repo.update_status(rec.id, EnrollmentStatus.approved)

    resp = client.post(
        "/enrollments/",
        json={"name": "Y", "cpf": "953.740.110-30", "age": 2},
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "already pending or approved" in resp.json()["detail"]


def test_two_rejections_allows_new(client):
    repo = EnrollmentRepository(DatabaseProvider.get_db())

    class DummyPayload:
        def model_dump(self):
            return {"name": "Z", "cpf": "652.535.790-01", "age": 12}

    for _ in range(2):
        rec = repo.create(DummyPayload())
        repo.update_rejection(rec.id, "too young")

    resp = client.post(
        "/enrollments/",
        json={"name": "Z", "cpf": "652.535.790-01", "age": 12},
    )
    assert resp.status_code == status.HTTP_201_CREATED


def test_list_empty_initially(client):
    resp = client.get("/enrollments/")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == []


def test_get_nonexistent_returns_404(client):
    resp = client.get("/enrollments/000000000000000000000000")
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_delete_nonexistent_returns_404(client):
    resp = client.delete("/enrollments/000000000000000000000000")
    assert resp.status_code == status.HTTP_404_NOT_FOUND
