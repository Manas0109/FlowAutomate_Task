from fastapi import APIRouter

from app.api.ws import router as ws_router
from app.api.chats_api import router as chat_router
from app.api.attachments_api import router as attachments_router
from app.api.users_api import router as users_router

api_router = APIRouter()
api_router.include_router(ws_router, tags=["websocket"])
api_router.include_router(chat_router, tags=["chat_router"])
api_router.include_router(attachments_router, tags=["attachments"])
api_router.include_router(users_router, tags=["users"])
