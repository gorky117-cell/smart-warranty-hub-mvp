from __future__ import annotations

import os
import hashlib
from pathlib import Path
from typing import Optional


def _local_dir() -> Path:
    base = os.getenv("OBJECT_STORE_LOCAL_DIR", "data/review_snapshots")
    path = Path(base)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def put_bytes(data: bytes, *, key: str, content_type: Optional[str] = None) -> str:
    """
    Store bytes to local FS or S3-compatible object storage.
    Returns a URI or path reference.
    """
    driver = os.getenv("OBJECT_STORE_DRIVER", "local").lower()
    if driver in ("s3", "r2", "minio"):
        try:
            import boto3  # type: ignore
        except Exception:
            driver = "local"
        else:
            bucket = os.getenv("OBJECT_STORE_S3_BUCKET")
            if not bucket:
                driver = "local"
            else:
                endpoint = os.getenv("OBJECT_STORE_S3_ENDPOINT")
                region = os.getenv("OBJECT_STORE_S3_REGION", "auto")
                access_key = os.getenv("OBJECT_STORE_S3_ACCESS_KEY")
                secret_key = os.getenv("OBJECT_STORE_S3_SECRET_KEY")
                client = boto3.client(
                    "s3",
                    endpoint_url=endpoint,
                    region_name=region,
                    aws_access_key_id=access_key,
                    aws_secret_access_key=secret_key,
                )
                key_norm = key.lstrip("/")
                extra = {}
                if content_type:
                    extra["ContentType"] = content_type
                client.put_object(Bucket=bucket, Key=key_norm, Body=data, **extra)
                return f"s3://{bucket}/{key_norm}"

    # local fallback
    base = _local_dir()
    safe_key = _hash_key(key)
    suffix = Path(key).suffix or ".bin"
    path = base / f"{safe_key}{suffix}"
    path.write_bytes(data)
    return str(path)
