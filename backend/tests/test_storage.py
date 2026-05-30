import os
import sys
import pytest

# Programmatically append the backend parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.storage_service import (
    ensure_bucket_exists, upload_file_content, download_file_content, generate_presigned_view_url
)
from app.core.config import settings


class TestMinIOStorageIntegration:
    def test_bucket_ensurance_and_file_flow(self):
        # 1. Verify bucket verification/creation runs successfully
        ensure_bucket_exists()

        # 2. Test file upload
        test_content = b"s3-minio-integration-test-data"
        object_key = "tests/test_file.txt"
        
        uploaded_key = upload_file_content(
            file_bytes=test_content,
            object_key=object_key,
            content_type="text/plain"
        )
        assert uploaded_key == object_key

        # 3. Test timed presigned URL generation
        presigned_url = generate_presigned_view_url(object_key, expiration=600)
        assert presigned_url != ""
        assert presigned_url.startswith("http://") or presigned_url.startswith("https://")
        assert settings.S3_BUCKET in presigned_url
        assert object_key in presigned_url

        # 4. Test file download and verify exact match
        downloaded_bytes = download_file_content(object_key)
        assert downloaded_bytes == test_content
