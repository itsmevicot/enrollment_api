from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.database import Database

from app.dependencies import get_db
from app.queue.provider import RabbitMQProvider


router = APIRouter(prefix = "/health", tags=["health"])


def check_rabbitmq():
    """
    Fast dependency that simply tries to open a RabbitMQ channel.
    Raises a 503 if it can’t.
    """
    try:
        RabbitMQProvider.get_channel()
    except Exception:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cannot connect to RabbitMQ",
        )
    return True


@router.get(
    path="/",
    summary="Health check",
    responses={
        200: {"description": "All systems operational"},
        503: {"description": "One or more dependencies are down"},
    },
)
def health(
    db: Database = Depends(get_db),
    _: bool = Depends(check_rabbitmq),
):
    """
    - Ping MongoDB via `db.client.admin.command("ping")`
    - Ensure RabbitMQ channel can be opened
    """
    try:
        db.client.admin.command("ping")
    except Exception:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cannot connect to MongoDB",
        )

    return {"status": "ok"}
