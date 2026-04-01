from pydantic import BaseModel, Field


class WsEnvelope(BaseModel):
    event: str = Field(..., description="Event description")
    room_id: str = Field(..., description="Unique roomid")
    payload: dict = Field(..., description="Content to share")
