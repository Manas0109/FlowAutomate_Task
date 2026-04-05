from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

from app.api.routes import api_router


def create_app() -> FastAPI:
    app = FastAPI(title="FlowAutomate Chat Backend", version="0.1.0")

    default_origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://chat-client-react.preview.emergentagent.com",
    ]
    configured_origins = [
        origin.strip()
        for origin in os.getenv("CORS_ALLOW_ORIGINS", "").split(",")
        if origin.strip()
    ]
    allow_origins = configured_origins or default_origins
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_origin_regex=r"https://.*\.preview\.emergentagent\.com",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    app.include_router(api_router)
    return app


app = create_app()
