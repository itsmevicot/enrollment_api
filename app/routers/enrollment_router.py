from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_enrollment_repo
from app.repositories.enrollment_repo import EnrollmentRepository
from app.schemas.enrollment_schema import EnrollmentCreate, EnrollmentRead
from app.services.enrollment_service import EnrollmentService

router = APIRouter(prefix="/enrollments", tags=["enrollments"])


def get_enrollment_service(
        repo: EnrollmentRepository = Depends(get_enrollment_repo),
) -> EnrollmentService:
    return EnrollmentService(repo)


@router.post("/", response_model=EnrollmentRead, status_code=status.HTTP_201_CREATED)
def create_enrollment(
        payload: EnrollmentCreate,
        service: EnrollmentService = Depends(get_enrollment_service),
):
    try:
        return service.create(payload)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/", response_model=List[EnrollmentRead])
def list_enrollments(service: EnrollmentService = Depends(get_enrollment_service)):
    return service.list()


@router.get("/{id}", response_model=EnrollmentRead)
def get_enrollment(id: str, service: EnrollmentService = Depends(get_enrollment_service)):
    result = service.get(id)
    if not result:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Enrollment not found")
    return result


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_enrollment(id: str, service: EnrollmentService = Depends(get_enrollment_service)):
    if not service.delete(id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Enrollment not found")
