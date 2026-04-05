from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.services import attachment_service

router = APIRouter(prefix="/api", tags=["attachments"])


# --- Request/Response schemas ---

class RequestUploadRequest(BaseModel):
    actor_user_id: str = Field(..., description="User ID requesting upload (TODO: replace with JWT)")
    filename: str = Field(..., description="Original filename")
    content_type: str = Field(..., description="MIME type (e.g., audio/mpeg, image/jpeg)")
    size_bytes: int = Field(..., ge=1, le=10_485_760, description="File size in bytes (max 10 MB)")


class RequestUploadResponse(BaseModel):
    upload_url: str
    attachment_id: str
    expires_at: str


class GetDownloadUrlResponse(BaseModel):
    url: str
    expires_at: str


# --- REST Endpoints ---

@router.post("/rooms/{room_id}/attachments/upload-url")
async def request_upload_url(
    room_id: str,
    body: RequestUploadRequest,
    db: AsyncSession = Depends(get_db_session),
) -> RequestUploadResponse:
    """Request a pre-signed upload URL for a new attachment.
    
    User must be a member of the room.
    File size must be ≤ 10 MB.
    Content type must be in allowed list (image, audio, video, pdf).
    """
    
    try:
        result = await attachment_service.request_upload(
            db=db,
            room_id=room_id,
            uploader_user_id=body.actor_user_id,
            filename=body.filename,
            content_type=body.content_type,
            size_bytes=body.size_bytes,
        )
        return RequestUploadResponse(**result)
    except attachment_service.AttachmentError as e:
        if "not a member" in str(e):
            raise HTTPException(status_code=403, detail=str(e))
        elif "Unsupported content type" in str(e):
            raise HTTPException(status_code=400, detail=str(e))
        elif "exceeds maximum size" in str(e):
            raise HTTPException(status_code=413, detail=str(e))
        else:
            raise HTTPException(status_code=400, detail=str(e))


@router.get("/rooms/{room_id}/attachments/{attachment_id}/url")
async def get_download_url(
    room_id: str,
    attachment_id: str,
    actor_user_id: str = Query(..., description="User ID requesting URL (TODO: replace with JWT)"),
    db: AsyncSession = Depends(get_db_session),
) -> GetDownloadUrlResponse:
    """Get a pre-signed download URL for an attachment.
    
    User must be a member of the room.
    Attachment must be in UPLOADED status.
    """
    
    try:
        result = await attachment_service.get_download_url(
            db=db,
            room_id=room_id,
            user_id=actor_user_id,
            attachment_id=attachment_id,
        )
        return GetDownloadUrlResponse(**result)
    except attachment_service.AttachmentError as e:
        if "not a member" in str(e):
            raise HTTPException(status_code=403, detail=str(e))
        elif "does not belong" in str(e):
            raise HTTPException(status_code=400, detail=str(e))
        else:
            raise HTTPException(status_code=400, detail=str(e))
    except attachment_service.AttachmentNotFoundError:
        raise HTTPException(status_code=404, detail="Attachment not found")
