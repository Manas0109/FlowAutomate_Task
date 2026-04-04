from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.group import Group
from app.models.message import Message
from app.models.user import User


async def save_message(
    db: AsyncSession,
    *,
    room_id: str,
    sender_external_id: str,
    text: str,
) -> Message:
    #get group if it exits
    group = await db.scalar(select(Group).where(Group.name == room_id))
    if group is None:
        raise ValueError("room_not_found")

    #get user/sender if it exits
    sender = await db.scalar(select(User).where(User.external_id == sender_external_id))
    if sender is None:
        raise ValueError("user_not_found")

    #save the message
    msg = Message(
        group_id=group.id,
        sender_user_id=sender.id,
        text=text.strip(),
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)

    #return the msg
    return msg

# ...existing code...
from sqlalchemy import desc, func

async def get_room_messages(
    db: AsyncSession,
    *,
    room_id: str,
    limit: int = 50,
) -> list[dict]:
    """Fetch latest messages for a room."""
    group = await db.scalar(select(Group).where(Group.name == room_id))
    if group is None:
        return []

    messages = await db.scalars(
        select(Message)
        .where(Message.group_id == group.id)
        .options(selectinload(Message.sender))  # eagerly load sender
        .order_by(desc(Message.created_at))
        .limit(limit)
    )
    
    return [
        {
            "message_id": msg.id,
            "text": msg.text,
            "user_id": msg.sender.external_id if msg.sender else "unknown",
            "created_at": msg.created_at.isoformat(),
        }
        for msg in reversed(list(messages))  # reverse to oldest-first
    ]