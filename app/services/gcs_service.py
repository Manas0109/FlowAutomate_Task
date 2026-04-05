import json
import os
from datetime import datetime, timedelta
from typing import Optional

from google.cloud import storage
from google.oauth2 import service_account

from app.core.config import settings


class GCSService:
    """Service for interacting with Google Cloud Storage."""
    
    def __init__(self):
        self.bucket_name = settings.gcs_bucket_name
        self.upload_expiry_minutes = settings.attachment_upload_expiry_minutes
        self.download_expiry_minutes = settings.attachment_download_expiry_minutes
        
        # Initialize GCS client using service account credentials from config
        sa_json = settings.gcs_service_account_json
        if not sa_json:
            raise RuntimeError(
                "GCS_SERVICE_ACCOUNT_JSON is not set in .env. "
                "Provide a file path or JSON string."
            )
        
        if os.path.isfile(sa_json):
            credentials = service_account.Credentials.from_service_account_file(sa_json)
        else:
            creds_dict = json.loads(sa_json)
            credentials = service_account.Credentials.from_service_account_info(creds_dict)
        
        self.client = storage.Client(
            credentials=credentials,
            project=credentials.project_id,
        )
        self.bucket = self.client.bucket(self.bucket_name)
    
    def generate_upload_url(
        self,
        storage_key: str,
        content_type: str,
    ) -> str:
        """Generate a pre-signed URL for uploading a file to GCS.
        
        Args:
            storage_key: GCS object path (e.g., "attachments/room-1/uuid/filename")
            content_type: MIME type (e.g., "audio/mpeg")
            
        Returns:
            Pre-signed PUT URL valid for UPLOAD_EXPIRY_MINUTES
        """
        blob = self.bucket.blob(storage_key)
        
        expiry = datetime.utcnow() + timedelta(minutes=self.upload_expiry_minutes)
        
        url = blob.generate_signed_url(
            version="v4",
            expiration=expiry,
            method="PUT",
            content_type=content_type,
        )
        
        return url
    
    def generate_download_url(
        self,
        storage_key: str,
    ) -> str:
        """Generate a pre-signed URL for downloading a file from GCS.
        
        Args:
            storage_key: GCS object path
            
        Returns:
            Pre-signed GET URL valid for DOWNLOAD_EXPIRY_MINUTES
        """
        blob = self.bucket.blob(storage_key)
        
        expiry = datetime.utcnow() + timedelta(minutes=self.download_expiry_minutes)
        
        url = blob.generate_signed_url(
            version="v4",
            expiration=expiry,
            method="GET",
        )
        
        return url
    
    def blob_exists(self, storage_key: str) -> bool:
        """Check if a blob exists in GCS.
        
        Args:
            storage_key: GCS object path
            
        Returns:
            True if blob exists, False otherwise
        """
        blob = self.bucket.blob(storage_key)
        return blob.exists()


# Singleton instance
_gcs_service: Optional[GCSService] = None


def get_gcs_service() -> GCSService:
    """Get or create the GCS service instance."""
    global _gcs_service
    if _gcs_service is None:
        _gcs_service = GCSService()
    return _gcs_service
