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

    # GCS / attachment settings
    gcs_bucket_name: str = Field("flowautomated-attachments", alias="GCS_BUCKET_NAME")
    gcs_service_account_json: str | None = Field(None, alias="GCS_SERVICE_ACCOUNT_JSON")
    attachment_upload_expiry_minutes: int = Field(15, alias="ATTACHMENT_UPLOAD_URL_EXPIRY_MINUTES")
    attachment_download_expiry_minutes: int = Field(60, alias="ATTACHMENT_DOWNLOAD_URL_EXPIRY_MINUTES")


settings = Settings()