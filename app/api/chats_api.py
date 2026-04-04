from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.services.message_service import get_room_messages

router = APIRouter(prefix="/api", tags=["chat"])


@router.get("/rooms/{room_id}/messages")
async def get_messages(
    room_id: str,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Fetch message history for a room."""
    messages = await get_room_messages(db, room_id=room_id, limit=limit)
    return {
        "room_id": room_id,
        "messages": messages,
        "count": len(messages),
    }