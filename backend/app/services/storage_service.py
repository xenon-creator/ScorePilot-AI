import logging
import boto3
import botocore
from botocore.client import Config
from app.core.config import settings

logger = logging.getLogger(__name__)

# Ensure endpoint URL format is robust for boto3 (requires schema, e.g., http://)
s3_endpoint = settings.S3_ENDPOINT
if s3_endpoint:
    if not s3_endpoint.startswith("http://") and not s3_endpoint.startswith("https://"):
        s3_endpoint = f"http://{s3_endpoint}"

logger.info(f"Connecting to S3/MinIO endpoint: {s3_endpoint}")

# Setup S3 Client with MinIO specific configs (path-style addressing, dummy region)
s3_client = None
try:
    if s3_endpoint:
        client = boto3.client(
            "s3",
            endpoint_url=s3_endpoint,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                connect_timeout=1,
                read_timeout=1,
                retries={"max_attempts": 0}
            ),
            region_name="us-east-1"  # Dummy region required by boto3
        )
        # Verify connection viability
        client.list_buckets()
        s3_client = client
except Exception as e:
    logger.warning(f"MinIO/S3 connection failed or endpoint unreachable: {e}")
    s3_client = None


def is_available() -> bool:
    """Returns True if the S3 client is initialized and available."""
    return s3_client is not None


def ensure_bucket_exists():
    """Idempotent bucket validation on startup, creates the bucket if missing."""
    if not is_available():
        logger.warning("MinIO/S3 not available - skipping bucket validation")
        return
    bucket_name = settings.S3_BUCKET
    try:
        s3_client.head_bucket(Bucket=bucket_name)
        logger.info(f"S3/MinIO bucket '{bucket_name}' verified successfully.")
    except botocore.exceptions.ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code in ["404", "403"]:  # Bucket not found or forbidden (need create)
            logger.info(f"S3/MinIO bucket '{bucket_name}' not found. Initializing bucket...")
            try:
                s3_client.create_bucket(Bucket=bucket_name)
                logger.info(f"S3/MinIO bucket '{bucket_name}' created successfully.")
            except Exception as create_err:
                logger.error(f"Failed to auto-create S3 bucket '{bucket_name}': {create_err}")
                raise create_err
        else:
            logger.error(f"Error validating S3/MinIO bucket '{bucket_name}': {e}")
            raise e


def upload_file_content(file_bytes: bytes, object_key: str, content_type: str = "application/pdf") -> str:
    """Upload raw file content bytes into S3 and return the generated object key."""
    if not is_available():
        raise RuntimeError("S3/MinIO storage is not available")
    try:
        s3_client.put_object(
            Bucket=settings.S3_BUCKET,
            Key=object_key,
            Body=file_bytes,
            ContentType=content_type
        )
        logger.info(f"File uploaded successfully to S3: {object_key}")
        return object_key
    except Exception as e:
        logger.error(f"Failed to upload file to S3: {e}")
        raise e


def generate_presigned_view_url(object_key: str, expiration: int = 3600) -> str:
    """Produce a secure dynamic presigned URL to securely render papers on frontend."""
    if not is_available() or not object_key:
        return ""
    try:
        url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.S3_BUCKET, "Key": object_key},
            ExpiresIn=expiration
        )
        return url
    except Exception as e:
        logger.error(f"Failed to generate presigned URL for S3 key '{object_key}': {e}")
        return ""


def download_file_content(object_key: str) -> bytes:
    """Retrieve raw file content bytes directly from S3/MinIO."""
    if not is_available():
        raise RuntimeError("S3/MinIO storage is not available")
    try:
        response = s3_client.get_object(Bucket=settings.S3_BUCKET, Key=object_key)
        return response["Body"].read()
    except Exception as e:
        logger.error(f"Failed to download object '{object_key}' from S3: {e}")
        raise e
