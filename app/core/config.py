from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "FlowAutomate Chat Backend"
    websocket_path: str = "/ws/{room_id}"


settings = Settings()
