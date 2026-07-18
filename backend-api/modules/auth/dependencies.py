from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from database import get_db
from modules.auth.models import Role, Tenant, User, UserStatus
from modules.auth.security import decode_access_token

bearer = HTTPBearer(auto_error=False)


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    user_id = decode_access_token(credentials.credentials) if credentials else None
    user = db.get(User, user_id) if user_id else None
    if not user or user.status != UserStatus.ACTIVE:
        raise HTTPException(401, "Phiên đăng nhập không hợp lệ")
    if user.tenant_id:
        tenant = db.get(Tenant, user.tenant_id)
        if not tenant or tenant.status != "ACTIVE":
            raise HTTPException(403, "Trường đang bị khóa")
    return user


def require_roles(*roles: Role):
    def dependency(user: User = Depends(current_user)):
        if user.role not in roles:
            raise HTTPException(403, "Bạn không có quyền thực hiện thao tác này")
        return user
    return dependency
