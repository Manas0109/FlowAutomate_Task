import os

from app.core.redis import get_redis_client

TYPING_TTL_SECONDS = int(os.getenv("TYPING_TTL_SECONDS", "3"))


def _typing_key(room_id: str, user_id: str) -> str:
    return f"typing:{room_id}:{user_id}"


async def start_typing(room_id: str, user_id: str) -> None:
    redis = get_redis_client()
    await redis.set(_typing_key(room_id, user_id), "1", ex=TYPING_TTL_SECONDS)


async def stop_typing(room_id: str, user_id: str) -> None:
    redis = get_redis_client()
    await redis.delete(_typing_key(room_id, user_id))