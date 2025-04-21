import os

import pytest
from fastapi.testclient import TestClient

from app.database.provider import DatabaseProvider
from app.dependencies import get_age_groups_client
from app.queue.provider import RabbitMQProvider
from main import app
from mongomock import MongoClient as MockClient

os.environ["ENVIRONMENT"] = "test"
os.environ["MONGO_DB_NAME"] = "test_db"
os.environ["AGE_GROUPS_API_URL"] = "http://fake-age-groups"

@pytest.fixture(autouse=True)
def dummy_rabbit(monkeypatch):
    """Stub out RabbitMQ so nothing actually gets sent."""
    class DummyChannel:
        def basic_publish(self, *args, **kwargs):
            pass

    monkeypatch.setattr(
        RabbitMQProvider,
        "get_channel",
        classmethod(lambda cls: DummyChannel()),
    )
    monkeypatch.setattr(
        RabbitMQProvider,
        "close",
        classmethod(lambda cls: None),
    )
    yield

@pytest.fixture
def age_groups_stub():
    """A stubbed AgeGroupsClient returning two buckets by default."""
    class StubClient:
        def __init__(self, groups):
            self._groups = groups

        def list(self):
            return self._groups

    return StubClient([
        {"min_age": 0, "max_age": 5},
        {"min_age": 10, "max_age": 20},
    ])

@pytest.fixture(autouse=True)
def override_age_groups(age_groups_stub):
    """Wire FastAPI to use our stub instead of the real AgeGroupsClient."""
    app.dependency_overrides[get_age_groups_client] = lambda: age_groups_stub
    yield
    app.dependency_overrides.clear()

@pytest.fixture(autouse=True)
def mock_mongo(monkeypatch):
    """
    Provide a single shared in‑memory MongoClient per test.
    """
    mock_client = MockClient()
    monkeypatch.setattr(
        DatabaseProvider,
        "get_client",
        classmethod(lambda cls: mock_client),
    )
    DatabaseProvider._client = mock_client
    yield
    DatabaseProvider._client = None

@pytest.fixture
def client():
    """TestClient bound to our FastAPI app."""
    return TestClient(app)
