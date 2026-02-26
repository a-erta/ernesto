"""
Storage abstraction.

If S3_BUCKET is set: uploads go to S3, URLs served via CloudFront.
Otherwise: falls back to local ./uploads/ directory (local dev).
"""
import uuid
import shutil
import structlog
from pathlib import Path
from typing import Optional

from fastapi import UploadFile

from .config import settings

log = structlog.get_logger()

LOCAL_UPLOAD_DIR = Path("./uploads")
LOCAL_UPLOAD_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

async def upload_image(file: UploadFile, user_id: str) -> str:
    """
    Upload an image and return a storage key/path.
    In S3 mode: returns the S3 object key.
    In local mode: returns the relative file path.
    """
    suffix = Path(file.filename).suffix.lower() if file.filename else ".jpg"
    filename = f"{uuid.uuid4()}{suffix}"

    if settings.use_s3:
        return await _upload_to_s3(file, user_id, filename)
    else:
        return await _upload_to_local(file, filename)


async def _upload_to_s3(file: UploadFile, user_id: str, filename: str) -> str:
    try:
        import aioboto3  # type: ignore
    except ImportError:
        log.error("storage.aioboto3_missing")
        raise RuntimeError("aioboto3 is required for S3 storage. Run: pip install aioboto3")

    key = f"uploads/{user_id}/{filename}"
    session = aioboto3.Session(
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
        region_name=settings.AWS_REGION,
    )
    async with session.client("s3") as s3:
        await s3.upload_fileobj(file.file, settings.S3_BUCKET, key)
    log.info("storage.s3_upload", key=key)
    return key


async def _upload_to_local(file: UploadFile, filename: str) -> str:
    dest = LOCAL_UPLOAD_DIR / filename
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    log.info("storage.local_upload", path=str(dest))
    return str(dest)


# ---------------------------------------------------------------------------
# URL resolution
# ---------------------------------------------------------------------------

def get_image_url(key: str) -> str:
    """
    Resolve a storage key to a publicly accessible URL.
    In S3 mode: returns a CloudFront URL.
    In local mode: returns a path relative to the /uploads static mount.
    """
    if settings.use_s3 and settings.CLOUDFRONT_DOMAIN:
        return f"https://{settings.CLOUDFRONT_DOMAIN}/{key}"
    if settings.use_s3:
        return f"https://{settings.S3_BUCKET}.s3.{settings.AWS_REGION}.amazonaws.com/{key}"
    # Local: key is the full path like "uploads/abc.jpg"
    filename = Path(key).name
    return f"/uploads/{filename}"
