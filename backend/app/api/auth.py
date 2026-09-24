"""Authenticated user API routes."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.auth.dependencies import CurrentUserDependency

router = APIRouter(prefix="/auth", tags=["auth"])


class AuthenticatedUser(BaseModel):
    id: str
    email: str | None


@router.get("/me", response_model=AuthenticatedUser)
async def get_authenticated_user(
    current_user: CurrentUserDependency,
) -> AuthenticatedUser:
    """Return the identity verified from the caller's Supabase token."""
    return AuthenticatedUser(id=current_user.id, email=current_user.email)
