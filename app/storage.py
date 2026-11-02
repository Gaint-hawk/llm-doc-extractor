"""Where uploaded PDFs live: local disk for development, S3 in AWS."""

import uuid
from pathlib import Path
from typing import Protocol

from app.config import settings


class Storage(Protocol):
    def save(self, data: bytes, filename: str) -> str: ...


class LocalStorage:
    def __init__(self, root: str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, data: bytes, filename: str) -> str:
        key = f"{uuid.uuid4().hex}-{Path(filename).name}"
        (self.root / key).write_bytes(data)
        return key


class S3Storage:
    def __init__(self, bucket: str):
        import boto3

        self.bucket = bucket
        self.s3 = boto3.client("s3")

    def save(self, data: bytes, filename: str) -> str:
        key = f"uploads/{uuid.uuid4().hex}-{Path(filename).name}"
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType="application/pdf")
        return key


def get_storage() -> Storage:
    if settings.storage_backend == "s3":
        if not settings.s3_bucket:
            raise RuntimeError("STORAGE_BACKEND=s3 requires S3_BUCKET")
        return S3Storage(settings.s3_bucket)
    return LocalStorage(settings.local_storage_dir)
