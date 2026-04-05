# Ensures Alembic sees all model metadata
from app.models.user import User
from app.models.group import Group
from app.models.membership import Membership, GroupRole
from app.models.message import Message, MessageType
from app.models.attachment import Attachment, UploadStatus

__all__ = ["User", "Group", "Membership", "GroupRole", "Message", "MessageType", "Attachment", "UploadStatus"]