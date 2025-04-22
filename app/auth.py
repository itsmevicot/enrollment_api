import json
from pathlib import Path

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

security = HTTPBasic()

_creds_path = Path(__file__).parent.parent / "credentials.json"
with open(_creds_path) as f:
    _USERS = json.load(f).get("users", {})


def get_current_user(
    credentials: HTTPBasicCredentials = Depends(security),
) -> str:
    """
    Validates against username/passwords in credentials.json.
    Raises 401 if invalid.
    Returns the username on success.
    """
    correct = _USERS.get(credentials.username)
    if not correct or credentials.password != correct:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username
