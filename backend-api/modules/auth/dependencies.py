"""Auth dependencies for FastAPI route injection.

Provides `current_user` — a Depends()-compatible callable that extracts and
validates the authenticated user from the request.  Currently a stub that
reads a header-based user ID; replace with real JWT verification later.
"""

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from .models import User


async def current_user(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
) -> User:
    """Return the authenticated User or raise 401.

    Stub implementation: trusts the ``X-User-Id`` header.  In production this
    MUST be replaced with proper JWT / session token verification.
    """
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")
    user = db.get(User, x_user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Người dùng không hợp lệ hoặc đã bị vô hiệu hóa")
    return user
