"""
S3 storage operations for document upload/download.
"""
import boto3
from botocore.config import Config
from django.conf import settings
import structlog

logger = structlog.get_logger()

# S3 client
def get_s3_client():
    """Get configured S3 client."""
    return boto3.client(
        's3',
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
        endpoint_url=settings.AWS_S3_ENDPOINT or None,
        config=Config(
            signature_version='s3v4',
            retries={'max_attempts': 3},
        ),
    )


def generate_presigned_upload_url(key: str, content_type: str, expires_in: int = 3600) -> dict:
    """Generate presigned URL for direct browser upload."""
    s3 = get_s3_client()

    # Set conditions for the upload
    conditions = [
        {"bucket": settings.AWS_S3_BUCKET},
        ["starts-with", "$key", key],
        {"Content-Type": content_type},
        ["content-length-range", 0, settings.MAX_UPLOAD_SIZE],
    ]

    # Generate presigned POST
    post = s3.generate_presigned_post(
        Bucket=settings.AWS_S3_BUCKET,
        Key=key,
        Fields={"Content-Type": content_type},
        Conditions=conditions,
        ExpiresIn=expires_in,
    )

    return {
        'url': post['url'],
        'fields': post['fields'],
    }


def generate_presigned_download_url(key: str, expires_in: int = 3600) -> str:
    """Generate presigned URL for download."""
    s3 = get_s3_client()

    url = s3.generate_presigned_url(
        'get_object',
        Params={'Bucket': settings.AWS_S3_BUCKET, 'Key': key},
        ExpiresIn=expires_in,
    )

    return url


def upload_to_s3(filepath: str, key: str, content_type: str = None, metadata: dict = None) -> bool:
    """Upload file to S3."""
    s3 = get_s3_client()

    extra_args = {}
    if content_type:
        extra_args['ContentType'] = content_type
    if metadata:
        extra_args['Metadata'] = {k: str(v) for k, v in metadata.items()}

    # Enable SSE-KMS if KMS key configured
    if settings.AWS_KMS_KEY_ID:
        extra_args['ServerSideEncryption'] = 'aws:kms'
        extra_args['SSEKMSKeyId'] = settings.AWS_KMS_KEY_ID

    try:
        s3.upload_file(filepath, settings.AWS_S3_BUCKET, key, ExtraArgs=extra_args)
        logger.info("File uploaded to S3", key=key)
        return True
    except Exception as e:
        logger.error("S3 upload failed", key=key, error=str(e))
        return False


def download_from_s3(key: str, filepath: str) -> bool:
    """Download file from S3."""
    s3 = get_s3_client()

    try:
        s3.download_file(settings.AWS_S3_BUCKET, key, filepath)
        logger.info("File downloaded from S3", key=key)
        return True
    except Exception as e:
        logger.error("S3 download failed", key=key, error=str(e))
        return False


def delete_from_s3(key: str) -> bool:
    """Delete file from S3."""
    s3 = get_s3_client()

    try:
        s3.delete_object(Bucket=settings.AWS_S3_BUCKET, Key=key)
        logger.info("File deleted from S3", key=key)
        return True
    except Exception as e:
        logger.error("S3 delete failed", key=key, error=str(e))
        return False


def check_s3_object_exists(key: str) -> bool:
    """Check if object exists in S3."""
    s3 = get_s3_client()

    try:
        s3.head_object(Bucket=settings.AWS_S3_BUCKET, Key=key)
        return True
    except Exception:
        return False