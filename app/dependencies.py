import httpx
from fastapi import Depends

from app.clients.age_group_client import AgeGroupClient
from app.config.settings import get_settings
from app.database.provider import DatabaseProvider
from app.repositories.enrollment_repo import EnrollmentRepository

settings = get_settings()

_http_client = httpx.Client(base_url=settings.age_groups_api_url)

def get_http_client() -> httpx.Client:
    return _http_client

def get_age_group_client(
    http_client: httpx.Client = Depends(get_http_client),
) -> AgeGroupClient:
    return AgeGroupClient(settings.age_groups_api_url, http_client)

def get_db():
    return DatabaseProvider.get_db()

def get_enrollment_repo(db=Depends(get_db)):
    return EnrollmentRepository(db)
