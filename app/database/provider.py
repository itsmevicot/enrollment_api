from contextlib import contextmanager
from pymongo import MongoClient
from pymongo.database import Database
from app.config.settings import get_settings

from mongomock import MongoClient as MockClient

_settings = get_settings()

class DatabaseProvider:
    _client: MongoClient | MockClient | None = None

    @classmethod
    def get_client(cls) -> MongoClient | MockClient:
        if cls._client is None:
            if _settings.environment == "test":
                cls._client = MockClient()
            else:
                cls._client = MongoClient(_settings.mongo_uri)
        return cls._client

    @classmethod
    def get_db(cls) -> Database:
        return cls.get_client()[_settings.mongo_db_name]

    @classmethod
    @contextmanager
    def session(cls):
        yield cls.get_db()
