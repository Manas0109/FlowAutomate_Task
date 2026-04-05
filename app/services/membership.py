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


def can_manage_members(role: GroupRole | None) -> bool:
    return role == GroupRole.ADMIN

def add_member(actor_user_id: str, room_id: str, target_user_id: str, role: GroupRole) -> None:
    actor_role = get_user_role(room_id, actor_user_id)
    if not can_manage_members(actor_role):
        raise PermissionError("Only ADMIN can add members")
    room = ROOM_MEMBERS.setdefault(room_id, {})
    if target_user_id in room:
        raise ValueError("User already a member")
    room[target_user_id] = role

def update_member_role(actor_user_id: str, room_id: str, target_user_id: str, new_role: GroupRole) -> None:
    actor_role = get_user_role(room_id, actor_user_id)
    if not can_manage_members(actor_role):
        raise PermissionError("Only ADMIN can update roles")
    room = ROOM_MEMBERS.get(room_id, {})
    if target_user_id not in room:
        raise ValueError("Target user is not a member")
    room[target_user_id] = new_role

def remove_member(actor_user_id: str, room_id: str, target_user_id: str) -> None:
    actor_role = get_user_role(room_id, actor_user_id)
    if not can_manage_members(actor_role):
        raise PermissionError("Only ADMIN can remove members")
    room = ROOM_MEMBERS.get(room_id, {})
    if target_user_id not in room:
        raise ValueError("Target user is not a member")
    del room[target_user_id]


def create_room(creator_user_id: str, target_user_id: str) -> str:
    """Create a DM room between two users. Returns deterministic room_id.
    Creator gets ADMIN, target gets WRITE. Idempotent — returns existing room_id if already exists.
    """
    a, b = sorted([creator_user_id, target_user_id])
    room_id = f"dm_{a}_{b}"
    if room_id not in ROOM_MEMBERS:
        ROOM_MEMBERS[room_id] = {
            creator_user_id: GroupRole.ADMIN,
            target_user_id: GroupRole.WRITE,
        }
    return room_id


def auto_join_user_to_room(room_id: str, user_id: str) -> GroupRole:
    """Auto-add user to an existing DM room if they try to join.
    Used when a user connects to WebSocket for a room they're not yet a member of.
    Returns the assigned role."""
    if room_id not in ROOM_MEMBERS:
        ROOM_MEMBERS[room_id] = {}
    
    # If already a member, return existing role
    if user_id in ROOM_MEMBERS[room_id]:
        return ROOM_MEMBERS[room_id][user_id]
    
    # Auto-add as WRITE member
    ROOM_MEMBERS[room_id][user_id] = GroupRole.WRITE
    return GroupRole.WRITE


def get_user_rooms(user_id: str) -> list[dict]:
    """Return all rooms the user is a member of, with their role."""
    return [
        {"room_id": room_id, "role": members[user_id]}
        for room_id, members in ROOM_MEMBERS.items()
        if user_id in members
    ]