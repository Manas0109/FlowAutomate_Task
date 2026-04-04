from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "FlowAutomate Chat Backend"
    websocket_path: str = "/ws/{room_id}"
    database_url: str = Field(..., alias="DATABASE_URL")  # required from env


settings = Settings()