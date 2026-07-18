import os

from sqlalchemy import select

from database import Base, SessionLocal, engine
from modules.auth.models import AuditLog, Role, User, UserStatus
from modules.auth.security import hash_password


def main():
    email = os.getenv("SUPERADMIN_EMAIL")
    password = os.getenv("SUPERADMIN_PASSWORD")
    if not email or not password or len(password) < 12:
        raise SystemExit("Đặt SUPERADMIN_EMAIL và SUPERADMIN_PASSWORD (ít nhất 12 ký tự)")
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.role == Role.SUPERADMIN)):
            raise SystemExit("Superadmin đã tồn tại; bootstrap chỉ được chạy một lần")
        user = User(email=email.lower(), password_hash=hash_password(password), display_name="Superadmin", role=Role.SUPERADMIN, tenant_id=None, status=UserStatus.ACTIVE)
        db.add(user); db.flush()
        db.add(AuditLog(actor_id=user.id, action="SUPERADMIN_BOOTSTRAPPED", resource_type="USER", resource_id=user.id, result="SUCCESS"))
        db.commit()
        print(f"Đã tạo Superadmin {email}")


if __name__ == "__main__":
    main()
