from contextlib import contextmanager
from pymongo import MongoClient
from pymongo.database import Database
from app.config.settings import get_settings

from mongomock import MongoClient as MockClient

class DatabaseProvider:
    _client: MongoClient | MockClient | None = None

    @classmethod
    def get_client(cls) -> MongoClient | MockClient:
        if cls._client is None:
            settings = get_settings()
            if settings.environment == "test":
                cls._client = MockClient()
            else:
                cls._client = MongoClient(settings.mongo_uri)
        return cls._client

    @classmethod
    def get_db(cls) -> Database:
        settings = get_settings()
        return cls.get_client()[settings.mongo_db_name]

    @classmethod
    @contextmanager
    def session(cls):
        yield cls.get_db()
