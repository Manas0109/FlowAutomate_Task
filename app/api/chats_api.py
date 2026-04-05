from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from app.db.session import get_db_session
from app.models.group import Group
from app.models.membership import GroupRole
from app.services import membership as membership_service
from app.services.message_service import get_room_messages


router = APIRouter(prefix="/api", tags=["chat"])


# --- Request body schemas ---

class CreateRoomRequest(BaseModel):
    # TODO: replace with JWT identity once auth is integrated
    creator_user_id: str
    target_user_id: str


class AddMemberRequest(BaseModel):
    # TODO: replace actor_user_id with JWT identity once auth is integrated
    actor_user_id: str
    target_user_id: str
    role: GroupRole


class UpdateMemberRoleRequest(BaseModel):
    # TODO: replace actor_user_id with JWT identity once auth is integrated
    actor_user_id: str
    role: GroupRole


# --- Room management ---

@router.post("/rooms")
async def create_room(
    body: CreateRoomRequest,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Create a DM room between two users (idempotent)."""
    if body.creator_user_id == body.target_user_id:
        raise HTTPException(status_code=400, detail="Cannot create a room with yourself")

    # Derive deterministic room_id (same logic as membership service)
    a, b = sorted([body.creator_user_id, body.target_user_id])
    room_id = f"dm_{a}_{b}"

    # Persist Group row if it doesn't exist yet
    existing = await db.scalar(select(Group).where(Group.name == room_id))
    if existing is None:
        db.add(Group(name=room_id))
        await db.commit()

    # Sync in-memory membership store
    membership_service.create_room(
        creator_user_id=body.creator_user_id,
        target_user_id=body.target_user_id,
    )

    return {"room_id": room_id, "creator": body.creator_user_id, "target": body.target_user_id}


@router.get("/rooms")
async def list_rooms(user_id: str = Query(...), db: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    """List all rooms the user is a member of, plus any DM rooms that exist in the database."""
    # Get explicitly joined rooms
    rooms = membership_service.get_user_rooms(user_id)
    
    # Also fetch DM rooms from database where user might be a participant
    # DM rooms follow pattern: dm_a_b where a and b are sorted usernames
    stmt = select(Group).where(Group.name.ilike(f"dm_%{user_id}%"))
    db_rooms = await db.scalars(stmt)
    
    room_ids = {room["room_id"] for room in rooms}
    for db_room in db_rooms:
        if db_room.name not in room_ids:
            # Auto-join user to this room
            role = membership_service.auto_join_user_to_room(db_room.name, user_id)
            rooms.append({
                "room_id": db_room.name,
                "role": role,
                "auto_joined": True  # Flag to indicate this was auto-discovered
            })
    
    return {"user_id": user_id, "rooms": rooms}


# --- Message history ---

@router.get("/rooms/{room_id}/messages")
async def get_messages(
    room_id: str,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Fetch message history for a room."""
    messages = await get_room_messages(db, room_id=room_id, limit=limit)
    return {
        "room_id": room_id,
        "messages": messages,
        "count": len(messages),
    }


# --- Admin membership management ---

@router.post("/rooms/{room_id}/members")
async def add_member(
    room_id: str,
    body: AddMemberRequest,
) -> dict[str, Any]:
    """Add a new member to a room. Actor must be ADMIN."""
    try:
        membership_service.add_member(
            actor_user_id=body.actor_user_id,
            room_id=room_id,
            target_user_id=body.target_user_id,
            role=body.role,
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {
        "room_id": room_id,
        "user_id": body.target_user_id,
        "role": body.role,
    }


@router.patch("/rooms/{room_id}/members/{target_user_id}")
async def update_member_role(
    room_id: str,
    target_user_id: str,
    body: UpdateMemberRoleRequest,
) -> dict[str, Any]:
    """Update a member's role. Actor must be ADMIN."""
    try:
        membership_service.update_member_role(
            actor_user_id=body.actor_user_id,
            room_id=room_id,
            target_user_id=target_user_id,
            new_role=body.role,
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {
        "room_id": room_id,
        "user_id": target_user_id,
        "role": body.role,
    }


@router.delete("/rooms/{room_id}/members/{target_user_id}")
async def remove_member(
    room_id: str,
    target_user_id: str,
    # TODO: replace with JWT identity once auth is integrated
    actor_user_id: str = Query(...),
) -> dict[str, Any]:
    """Remove a member from a room. Actor must be ADMIN."""
    try:
        membership_service.remove_member(
            actor_user_id=actor_user_id,
            room_id=room_id,
            target_user_id=target_user_id,
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"room_id": room_id, "removed_user_id": target_user_id}
