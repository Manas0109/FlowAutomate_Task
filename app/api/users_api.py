from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.models.user import User

router = APIRouter(prefix="/api", tags=["users"])


class RegisterRequest(BaseModel):
    username: str  # used as both external_id and display_name


@router.post("/users/register")
async def register_user(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Find or create a user by username. Idempotent — safe to call on every login."""
    username = body.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="username cannot be empty")

    user = await db.scalar(select(User).where(User.external_id == username))
    if user is None:
        user = User(external_id=username, display_name=username)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        created = True
    else:
        created = False

    return {
        "user_id": user.external_id,
        "display_name": user.display_name,
        "created": created,
    }
