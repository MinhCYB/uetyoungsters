import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from modules.auth.dependencies import current_user
from modules.auth.models import AuditLog, Invitation, RefreshToken, Role, User, UserStatus
from modules.auth.security import hash_password, hash_token, make_access_token, verify_password
from modules.candidate.models import CandidateProfile

router = APIRouter(prefix="/api/auth", tags=["auth"])


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class Registration(Credentials):
    display_name: str = Field(min_length=2, max_length=160)
    graduated: Literal[True]


class AcceptInvitation(BaseModel):
    password: str = Field(min_length=8, max_length=128)


def public_user(user: User):
    return {"id": user.id, "email": user.email, "displayName": user.display_name, "role": user.role.value, "tenantId": user.tenant_id, "mustChangePassword": user.must_change_password}


def issue_session(user: User, db: Session, response: Response):
    raw_refresh = secrets.token_urlsafe(48)
    db.add(RefreshToken(token_hash=hash_token(raw_refresh), user_id=user.id, expires_at=datetime.now(timezone.utc) + timedelta(days=14)))
    db.commit()
    response.set_cookie("cc_refresh", raw_refresh, httponly=True, secure=os.getenv("COOKIE_SECURE", "false").lower() == "true", samesite="lax", max_age=14 * 86400, path="/api/auth")
    return {"accessToken": make_access_token(user.id), "user": public_user(user)}


@router.post("/register/professional", status_code=201)
def register(payload: Registration, response: Response, db: Session = Depends(get_db)):
    email = payload.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "Email đã được sử dụng")
    user = User(email=email, password_hash=hash_password(payload.password), display_name=payload.display_name, role=Role.PROFESSIONAL, tenant_id=None, status=UserStatus.ACTIVE, email_verified_at=datetime.now(timezone.utc))
    db.add(user); db.flush()
    db.add(CandidateProfile(user_id=user.id, tenant_id=None, class_id=None, profile_type="PROFESSIONAL"))
    db.commit(); db.refresh(user)
    return issue_session(user, db, response)


@router.post("/login")
def login(payload: Credentials, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Email hoặc mật khẩu không đúng")
    if user.status != UserStatus.ACTIVE:
        raise HTTPException(403, "Tài khoản chưa hoạt động hoặc đã bị khóa")
    user.last_login_at = datetime.now(timezone.utc); db.commit()
    return issue_session(user, db, response)


@router.post("/refresh")
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    raw = request.cookies.get("cc_refresh")
    token = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw or "")))
    now = datetime.now(timezone.utc)
    if not token or token.revoked_at or token.expires_at.replace(tzinfo=timezone.utc) <= now:
        raise HTTPException(401, "Refresh token không hợp lệ")
    user = db.get(User, token.user_id)
    if not user or user.status != UserStatus.ACTIVE:
        raise HTTPException(401, "Tài khoản không hoạt động")
    token.revoked_at = now; db.commit()
    return issue_session(user, db, response)


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    raw = request.cookies.get("cc_refresh")
    token = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw or "")))
    if token: token.revoked_at = datetime.now(timezone.utc); db.commit()
    response.delete_cookie("cc_refresh", path="/api/auth")


@router.get("/me")
def me(user: User = Depends(current_user)):
    return public_user(user)


@router.post("/invitations/{token}/accept")
def accept_invitation(token: str, payload: AcceptInvitation, response: Response, db: Session = Depends(get_db)):
    invitation = db.scalar(select(Invitation).where(Invitation.token_hash == hash_token(token)))
    now = datetime.now(timezone.utc)
    if not invitation or invitation.accepted_at or invitation.expires_at.replace(tzinfo=timezone.utc) <= now:
        raise HTTPException(400, "Lời mời không hợp lệ hoặc đã hết hạn")
    if db.scalar(select(User).where(User.email == invitation.email)):
        raise HTTPException(409, "Email đã có tài khoản")
    user = User(email=invitation.email, display_name=invitation.display_name, password_hash=hash_password(payload.password), role=invitation.role, tenant_id=invitation.tenant_id, status=UserStatus.ACTIVE, email_verified_at=now, created_by=invitation.invited_by)
    db.add(user); db.flush()
    if invitation.role == Role.STUDENT:
        profile_type = invitation.profile_type or "HIGH_SCHOOL"
        profile_data = dict(invitation.profile_data or {})
        db.add(CandidateProfile(user_id=user.id, tenant_id=invitation.tenant_id, class_id=invitation.class_id, profile_type=profile_type, **profile_data))
    invitation.accepted_at = now
    db.add(AuditLog(actor_id=invitation.invited_by, tenant_id=invitation.tenant_id, action="INVITATION_ACCEPTED", resource_type="USER", resource_id=user.id))
    db.commit(); db.refresh(user)
    return issue_session(user, db, response)


@router.post("/forgot-password", status_code=202)
def forgot_password():
    return {"message": "Nếu email tồn tại, hướng dẫn đặt lại mật khẩu sẽ được gửi."}
