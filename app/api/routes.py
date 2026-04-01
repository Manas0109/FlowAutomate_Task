from fastapi import APIRouter

from app.api.ws import router as ws_router

api_router = APIRouter()
api_router.include_router(ws_router, tags=["websocket"])
