import uuid
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.models.attachment import Attachment, UploadStatus
from app.services.gcs_service import get_gcs_service
from app.services import membership as membership_service


# Allowed file types
ALLOWED_CONTENT_TYPES = {
    "image/jpeg", "image/png", "image/webp", "image/gif",
    "audio/mpeg", "audio/ogg", "audio/webm",
    "video/mp4", "video/webm",
    "application/pdf",
}

# Max upload size: 10 MB
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024


class AttachmentError(Exception):
    """Base exception for attachment operations."""
    pass


class AttachmentNotFoundError(AttachmentError):
    """Attachment not found."""
    pass


class AttachmentAlreadyUsedError(AttachmentError):
    """Attachment already linked to a message."""
    pass


class InvalidAttachmentError(AttachmentError):
    """Invalid attachment state or properties."""
    pass


async def request_upload(
    db: AsyncSession,
    room_id: str,
    uploader_user_id: str,
    filename: str,
    content_type: str,
    size_bytes: int,
) -> dict:
    """Request a pre-signed upload URL for a new attachment.
    
    Args:
        db: DB session
        room_id: Room ID
        uploader_user_id: User ID of uploader
        filename: Original filename
        content_type: MIME type
        size_bytes: File size in bytes
        
    Returns:
        { upload_url, attachment_id, expires_at }
        
    Raises:
        AttachmentError: If validation fails
    """
    
    # Validate membership
    if not membership_service.is_room_member(room_id, uploader_user_id):
        raise AttachmentError("User is not a member of this room")
    
    # Validate content type
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise AttachmentError(f"Unsupported content type: {content_type}")
    
    # Validate file size
    if size_bytes > MAX_FILE_SIZE_BYTES:
        raise AttachmentError(f"File exceeds maximum size of 10 MB")
    
    if size_bytes <= 0:
        raise AttachmentError("File size must be greater than 0")
    
    # Generate storage key
    att_id = str(uuid.uuid4())
    storage_key = f"attachments/{room_id}/{att_id}/{filename}"
    
    # Generate upload URL
    gcs = get_gcs_service()
    upload_url = gcs.generate_upload_url(storage_key, content_type)
    
    # Create attachment record
    attachment = Attachment(
        id=uuid.uuid4(),
        room_id=room_id,
        uploader_user_id=uploader_user_id,
        filename=filename,
        content_type=content_type,
        size_bytes=size_bytes,
        storage_key=storage_key,
        upload_status=UploadStatus.PENDING,
    )
    
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)
    
    return {
        "upload_url": upload_url,
        "attachment_id": str(attachment.id),
        "expires_at": (datetime.utcnow() + timedelta(minutes=settings.attachment_upload_expiry_minutes)).isoformat() + "Z",
    }


async def confirm_upload(
    db: AsyncSession,
    attachment_id: str,
    uploader_user_id: str,
) -> None:
    """Mark an attachment as uploaded.
    
    Args:
        db: DB session
        attachment_id: UUID of attachment
        uploader_user_id: User who uploaded the file
        
    Raises:
        AttachmentNotFoundError: If attachment not found
        AttachmentError: If validation fails
    """
    
    stmt = select(Attachment).where(Attachment.id == attachment_id)
    result = await db.execute(stmt)
    attachment = result.scalar_one_or_none()
    
    if not attachment:
        raise AttachmentNotFoundError(f"Attachment {attachment_id} not found")
    
    # Verify uploader
    if attachment.uploader_user_id != uploader_user_id:
        raise AttachmentError("Only the uploader can confirm upload")
    
    # Mark as uploaded
    attachment.upload_status = UploadStatus.UPLOADED
    await db.commit()


async def get_download_url(
    db: AsyncSession,
    room_id: str,
    user_id: str,
    attachment_id: str,
) -> dict:
    """Get a pre-signed download URL for an attachment.
    
    Args:
        db: DB session
        room_id: Room ID
        user_id: User requesting download
        attachment_id: UUID of attachment
        
    Returns:
        { url, expires_at }
        
    Raises:
        AttachmentError: If validation fails
    """
    
    # Check membership
    if not membership_service.is_room_member(room_id, user_id):
        raise AttachmentError("User is not a member of this room")
    
    # Look up attachment
    stmt = select(Attachment).where(Attachment.id == attachment_id)
    result = await db.execute(stmt)
    attachment = result.scalar_one_or_none()
    
    if not attachment:
        raise AttachmentNotFoundError(f"Attachment {attachment_id} not found")
    
    # Verify it belongs to this room
    if attachment.room_id != room_id:
        raise AttachmentError("Attachment does not belong to this room")
    
    # Verify it's uploaded
    if attachment.upload_status != UploadStatus.UPLOADED:
        raise AttachmentError("Attachment is not yet available for download")
    
    # Generate download URL
    gcs = get_gcs_service()
    download_url = gcs.generate_download_url(attachment.storage_key)
    
    return {
        "url": download_url,
        "expires_at": (datetime.utcnow() + timedelta(minutes=settings.attachment_download_expiry_minutes)).isoformat() + "Z",
    }


async def get_attachment_by_id(
    db: AsyncSession,
    attachment_id: str,
) -> Attachment:
    """Look up an attachment by ID.
    
    Args:
        db: DB session
        attachment_id: UUID of attachment
        
    Returns:
        Attachment record
        
    Raises:
        AttachmentNotFoundError: If not found
    """
    
    stmt = select(Attachment).where(Attachment.id == attachment_id)
    result = await db.execute(stmt)
    attachment = result.scalar_one_or_none()
    
    if not attachment:
        raise AttachmentNotFoundError(f"Attachment {attachment_id} not found")
    
    return attachment
