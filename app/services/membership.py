from app.models.membership import GroupRole

# Temporary in-memory membership store (Phase 3 stub)
# room_id -> user_id -> role
ROOM_MEMBERS: dict[str, dict[str, GroupRole]] = {
    "room-1": {
        "u1": GroupRole.WRITE,
        "u2": GroupRole.WRITE,
        "u3": GroupRole.READ,
    }
}


def get_user_role(room_id: str, user_id: str) -> GroupRole | None:
    """Get the role of a user in a room."""
    room = ROOM_MEMBERS.get(room_id, {})
    return room.get(user_id)


def is_room_member(room_id: str, user_id: str) -> bool:
    """Check if a user is a member of a room."""
    return get_user_role(room_id, user_id) is not None
