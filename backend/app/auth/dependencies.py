"""FastAPI dependencies for authenticating Supabase users."""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase_auth.errors import AuthError

from app.database.supabase import create_user_client

_bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True)
class CurrentUser:
    id: str
    email: str | None
    access_token: str


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing bearer token",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(_bearer_scheme),
    ],
) -> CurrentUser:
    """Verify a Supabase access token and return the authenticated user."""
    if credentials is None:
        raise _unauthorized()

    access_token = credentials.credentials
    client = await create_user_client(access_token)

    try:
        response = await client.auth.get_user(access_token)
    except AuthError as exc:
        raise _unauthorized() from exc

    if response is None:
        raise _unauthorized()

    return CurrentUser(
        id=response.user.id,
        email=response.user.email,
        access_token=access_token,
    )


# Use this annotation on every chat and retrieval route so authentication finishes
# before FastAPI invokes the endpoint handler.
CurrentUserDependency = Annotated[CurrentUser, Depends(get_current_user)]
