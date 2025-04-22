from fastapi import status
from fastapi.testclient import TestClient

from app.database.provider import DatabaseProvider
from app.dependencies import get_age_groups_client
from app.enums.enrollment_status import EnrollmentStatus
from app.queue.provider import RabbitMQProvider
from app.repositories.enrollment_repo import EnrollmentRepository
from main import app


def test_health_success(client: TestClient):
    r = client.get("/health/", auth=("admin", "commonuser"))
    assert r.status_code == status.HTTP_200_OK
    assert r.json() == {"status": "ok"}


def test_health_mongo_down(client: TestClient, monkeypatch):
    class BadDB:
        client = type("c", (), {
            "admin": type("a", (), {
                "command": staticmethod(lambda cmd: (_ for _ in ()).throw(Exception("fail")))
            })
        })
    monkeypatch.setattr(DatabaseProvider, "get_db", classmethod(lambda cls: BadDB()))
    r = client.get("/health/", auth=("admin", "commonuser"))
    assert r.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert "MongoDB" in r.json()["detail"]


def test_health_rabbit_down(client: TestClient, monkeypatch):
    monkeypatch.setattr(
        RabbitMQProvider,
        "get_channel",
        classmethod(lambda cls: (_ for _ in ()).throw(Exception("no rabbit")))
    )
    r = client.get("/health/", auth=("admin", "commonuser"))
    assert r.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert "RabbitMQ" in r.json()["detail"]


def test_create_fetch_delete_full_cycle(client: TestClient):
    payload = {"name": "Alice", "cpf": "652.535.790-01", "age": 12}
    r = client.post(
        "/enrollments/", json=payload, auth=("admin", "commonuser")
    )
    assert r.status_code == status.HTTP_201_CREATED
    body = r.json()

    assert body["name"] == "Alice"
    assert body["cpf"] == "65253579001"
    assert body["age"] == 12
    assert body["status"] == EnrollmentStatus.pending.value
    assert body.get("rejection_reason") is None

    eid = body["id"]
    lst = client.get(
        "/enrollments/", auth=("admin", "commonuser")
    ).json()
    assert any(e["id"] == eid for e in lst)

    one = client.get(
        f"/enrollments/{eid}", auth=("admin", "commonuser")
    ).json()
    assert one["id"] == eid

    d = client.delete(
        f"/enrollments/{eid}", auth=("admin", "commonuser")
    )
    assert d.status_code == status.HTTP_204_NO_CONTENT
    assert client.get(
        f"/enrollments/{eid}", auth=("admin", "commonuser")
    ).status_code == status.HTTP_404_NOT_FOUND


def test_duplicate_pending_blocks(client: TestClient):
    p = {"name": "Bob", "cpf": "953.740.110-30", "age": 2}
    r1 = client.post(
        "/enrollments/", json=p, auth=("admin", "commonuser")
    )
    assert r1.status_code == status.HTTP_201_CREATED

    r2 = client.post(
        "/enrollments/", json=p, auth=("admin", "commonuser")
    )
    assert r2.status_code == status.HTTP_400_BAD_REQUEST
    assert "already pending" in r2.json()["detail"]


def test_too_many_rejections_blocks(client: TestClient):
    repo = EnrollmentRepository(DatabaseProvider.get_db())
    class DummyPayload:
        def model_dump(self):
            return {"name": "X", "cpf": "920.104.720-71", "age": 5}

    for _ in range(3):
        rec = repo.create(DummyPayload(), owner="admin")
        repo.update_rejection(rec.id, "reason")

    r = client.post(
        "/enrollments/", json={"name":"X","cpf":"920.104.720-71","age":5},
        auth=("admin", "commonuser")
    )
    assert r.status_code == status.HTTP_400_BAD_REQUEST
    assert "Too many rejections" in r.json()["detail"]


def test_invalid_cpf_422(client: TestClient):
    r = client.post(
        "/enrollments/", json={"name":"Z","cpf":"00000000000","age":5},
        auth=("admin", "commonuser")
    )
    assert r.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_create_when_no_age_groups(client: TestClient, age_groups_stub):
    empty = age_groups_stub
    empty._groups = []
    app.dependency_overrides[get_age_groups_client] = lambda: empty

    r = client.post(
        "/enrollments/", json={"name":"NoGroups","cpf":"274.427.600-66","age":30},
        auth=("admin", "commonuser")
    )
    assert r.status_code == status.HTTP_201_CREATED


def test_duplicate_approved_blocks(client: TestClient):
    repo = EnrollmentRepository(DatabaseProvider.get_db())
    class DummyPayload:
        def model_dump(self):
            return {"name": "Y", "cpf": "953.740.110-30", "age": 2}

    rec = repo.create(DummyPayload(), owner="admin")
    repo.update_status(rec.id, EnrollmentStatus.approved)

    resp = client.post(
        "/enrollments/", json={"name": "Y", "cpf": "953.740.110-30", "age": 2},
        auth=("admin", "commonuser")
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "already pending or approved" in resp.json()["detail"]


def test_two_rejections_allows_new(client: TestClient):
    repo = EnrollmentRepository(DatabaseProvider.get_db())
    class DummyPayload:
        def model_dump(self):
            return {"name": "Z", "cpf": "652.535.790-01", "age": 12}

    for _ in range(2):
        rec = repo.create(DummyPayload(), owner="admin")
        repo.update_rejection(rec.id, "too young")

    resp = client.post(
        "/enrollments/", json={"name": "Z", "cpf": "652.535.790-01", "age": 12},
        auth=("admin", "commonuser")
    )
    assert resp.status_code == status.HTTP_201_CREATED


def test_list_empty_initially(client: TestClient):
    resp = client.get(
        "/enrollments/", auth=("admin", "commonuser")
    )
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == []


def test_get_nonexistent_returns_404(client: TestClient):
    resp = client.get(
        "/enrollments/000000000000000000000000", auth=("admin", "commonuser")
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_delete_nonexistent_returns_404(client: TestClient):
    resp = client.delete(
        "/enrollments/000000000000000000000000", auth=("admin", "commonuser")
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND

def test_user_cannot_access_others_enrollment(client: TestClient):
    r_admin = client.post(
        "/enrollments/", json={"name": "AdminOnly", "cpf": "761.302.340-07", "age": 12},
        auth=("admin", "commonuser")
    )
    assert r_admin.status_code == status.HTTP_201_CREATED
    admin_id = r_admin.json()["id"]

    list_user1 = client.get("/enrollments/", auth=("user1", "commonpass"))
    assert list_user1.status_code == status.HTTP_200_OK
    assert all(e["id"] != admin_id for e in list_user1.json())

    get_user1 = client.get(f"/enrollments/{admin_id}", auth=("user1", "commonpass"))
    assert get_user1.status_code == status.HTTP_404_NOT_FOUND

    del_user1 = client.delete(f"/enrollments/{admin_id}", auth=("user1", "commonpass"))
    assert del_user1.status_code == status.HTTP_404_NOT_FOUND

    get_admin = client.get(f"/enrollments/{admin_id}", auth=("admin", "commonuser"))
    assert get_admin.status_code == status.HTTP_200_OK
    del_admin = client.delete(f"/enrollments/{admin_id}", auth=("admin", "commonuser"))
    assert del_admin.status_code == status.HTTP_204_NO_CONTENT


def test_user_can_see_and_delete_only_their_own_enrollment(client: TestClient):
    r_user1 = client.post(
        "/enrollments/", json={"name": "UserOne", "cpf": "154.213.240-10", "age": 10},
        auth=("user1", "commonpass")
    )
    assert r_user1.status_code == status.HTTP_201_CREATED
    user1_id = r_user1.json()["id"]

    list_u1 = client.get("/enrollments/", auth=("user1", "commonpass"))
    assert any(e["id"] == user1_id for e in list_u1.json())

    list_admin2 = client.get("/enrollments/", auth=("admin", "commonuser"))
    assert all(e["id"] != user1_id for e in list_admin2.json())

    del_u1 = client.delete(f"/enrollments/{user1_id}", auth=("user1", "commonpass"))
    assert del_u1.status_code == status.HTTP_204_NO_CONTENT

    get_u1 = client.get(f"/enrollments/{user1_id}", auth=("user1", "commonpass"))
    assert get_u1.status_code == status.HTTP_404_NOT_FOUND
