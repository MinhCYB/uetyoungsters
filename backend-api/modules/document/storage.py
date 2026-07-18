import os
from datetime import timedelta
from functools import lru_cache
from io import BytesIO

from minio import Minio
from minio.error import S3Error


class DocumentStorage:
    def __init__(self):
        self.bucket = os.getenv("MINIO_BUCKET", "career-compass-documents")
        self.client = Minio(
            os.getenv("MINIO_ENDPOINT", "localhost:9000"),
            access_key=os.getenv("MINIO_ACCESS_KEY", "career_compass"),
            secret_key=os.getenv("MINIO_SECRET_KEY", "career_compass_dev_secret"),
            secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
        )

    def ensure_bucket(self) -> None:
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    def put(self, key: str, content: bytes, content_type: str) -> None:
        self.ensure_bucket()
        self.client.put_object(self.bucket, key, BytesIO(content), len(content), content_type=content_type)

    def get(self, key: str) -> bytes:
        response = self.client.get_object(self.bucket, key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def delete(self, key: str) -> None:
        try:
            self.client.remove_object(self.bucket, key)
        except S3Error:
            pass

    def presigned_get(self, key: str, expires: timedelta) -> str:
        return self.client.presigned_get_object(self.bucket, key, expires=expires)


@lru_cache(maxsize=1)
def document_storage() -> DocumentStorage:
    return DocumentStorage()
