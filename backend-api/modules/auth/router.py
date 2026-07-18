"""Auth router — login, register, profile endpoints.

Prefix: /api/auth (set here, mounted without additional prefix in main.py).
Skeleton only — business logic to be implemented separately.
"""

from fastapi import APIRouter, Depends

from .dependencies import current_user
from .models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register")
def register():
    """Register a new user account. TODO: implement."""
    return {"status": "not_implemented"}


@router.post("/login")
def login():
    """Authenticate and return tokens. TODO: implement."""
    return {"status": "not_implemented"}


@router.get("/me")
def me(user: User = Depends(current_user)):
    """Return the current authenticated user's profile."""
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "display_name": user.display_name,
        "tenant_id": user.tenant_id,
    }
