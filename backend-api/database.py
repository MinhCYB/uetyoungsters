"""Kết nối database dùng chung cho toàn bộ backend-api (không riêng cho module nào).

DATABASE_URL lấy từ biến môi trường, đã được set sẵn trong docker-compose.yml
(postgresql://cc_user:cc_pass@db:5432/career_compass). Khi chạy local ngoài
docker-compose, có thể override bằng cách export DATABASE_URL trước khi start.
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://cc_user:cc_pass@localhost:5432/career_compass"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Tạo các bảng của tất cả module đã đăng ký models qua Base.

    Import model modules ở đây (thay vì import ở top-level) để tránh vòng lặp
    import: các module con import `Base` từ file này, còn file này cần các
    class model đã được định nghĩa trước khi gọi create_all.
    """
    from modules.assessment import models as assessment_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
