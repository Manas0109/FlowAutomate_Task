from fastapi import APIRouter

from app.api.ws import router as ws_router
from app.api.chats_api import router as chat_router

api_router = APIRouter()
api_router.include_router(ws_router, tags=["websocket"])
api_router.include_router(chat_router, tags=["chat_router"])
