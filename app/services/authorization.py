from app.models.membership import GroupRole


def can_send_message(role: GroupRole) -> bool:
    return role in {GroupRole.ADMIN, GroupRole.WRITE}
