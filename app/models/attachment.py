from enum import Enum
from uuid import uuid4

from sqlalchemy import Column, String, Integer, Enum as SQLEnum, DateTime, func
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class UploadStatus(str, Enum):
    """Status of file upload to GCS."""
    PENDING = "pending"
    UPLOADED = "uploaded"
    FAILED = "failed"


class Attachment(Base):
    """File attachment metadata. Represents a file uploaded to GCS."""
    
    __tablename__ = "attachments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    room_id = Column(String, nullable=False, index=True)
    uploader_user_id = Column(String, nullable=False)
    filename = Column(String, nullable=False)
    content_type = Column(String, nullable=False)  # e.g. "audio/mpeg", "image/jpeg"
    size_bytes = Column(Integer, nullable=False)  # validated ≤ 10MB
    storage_key = Column(String, nullable=False, unique=True)  # GCS object path
    upload_status = Column(
        SQLEnum(UploadStatus, name="upload_status", create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=UploadStatus.PENDING,
    )
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    
    def __repr__(self) -> str:
        return f"<Attachment(id={self.id}, room_id={self.room_id}, filename={self.filename}, status={self.upload_status})>"
