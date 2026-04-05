from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from uuid import UUID

from app.models.group import Group
from app.models.message import Message, MessageType
from app.models.user import User


async def save_message(
    db: AsyncSession,
    *,
    room_id: str,
    sender_external_id: str,
    text: str | None = None,
    message_type: MessageType | None = None,
    attachment_id: str | UUID | None = None,
) -> Message:
    """Save a message to the database.
    
    Args:
        db: DB session
        room_id: Room ID (group name)
        sender_external_id: External user ID of sender
        text: Message text (for TEXT messages)
        message_type: MessageType enum (TEXT or ATTACHMENT)
        attachment_id: UUID of attachment (for ATTACHMENT messages)
        
    Returns:
        Saved Message object
        
    Raises:
        ValueError: If room or user not found, or invalid message type
    """
    
    # Default to TEXT if not specified
    if message_type is None:
        message_type = MessageType.TEXT
    
    # Validate message type and content
    if message_type == MessageType.TEXT and not text:
        raise ValueError("text is required for TEXT messages")
    
    if message_type == MessageType.ATTACHMENT and not attachment_id:
        raise ValueError("attachment_id is required for ATTACHMENT messages")
    
    # Get group
    group = await db.scalar(select(Group).where(Group.name == room_id))
    if group is None:
        raise ValueError("room_not_found")

    # Get user/sender
    sender = await db.scalar(select(User).where(User.external_id == sender_external_id))
    if sender is None:
        raise ValueError("user_not_found")

    # Convert attachment_id to UUID if it's a string
    if attachment_id and isinstance(attachment_id, str):
        try:
            attachment_id = UUID(attachment_id)
        except (ValueError, TypeError):
            raise ValueError("invalid_attachment_id")

    # Save the message
    msg = Message(
        group_id=group.id,
        sender_user_id=sender.id,
        text=text.strip() if text else None,
        message_type=message_type,
        attachment_id=attachment_id,
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)

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