from pydantic import BaseModel, Field
from typing import Optional, Any


class WsMessage(BaseModel):
    event: str = Field(..., description="Event description")
    room_id: str = Field(..., description="Unique roomid")
    payload: dict = Field(..., description="Content to share")
    meta: dict[str, Any] | None = None
