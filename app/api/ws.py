from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Any
from app.schemas.events import WsMessage
from pydantic import ValidationError
from app.services.authorization import can_send_message
from app.services.membership import get_user_role
from app.realtime.connection_manager import ConnectionManager
from app.db.session import get_db
from app.services.message_service import save_message
from app.services import membership as membership_service
from app.services import typing_service
from app.services import attachment_service
from app.models.message import MessageType
from app.models.membership import GroupRole
from app.models.group import Group
from sqlalchemy import select


router = APIRouter()

connection_manager = ConnectionManager()

@router.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str) -> None:
    user_id = websocket.query_params.get("user_id")

    #No user_id present in query param
    if not user_id:
        await websocket.accept()
        await websocket.send_json(
                    build_error_response(
                        room_id=room_id,
                        code="missing_user_id",
                        message="Query param 'user_id' required",       
                    )
                )
        await websocket.close(code=1008)
        return

    #User is not part of this room_id
    role = get_user_role(room_id, user_id)
    
    # If user not in room, try to auto-add them if room exists in database
    if role is None:
        db = await get_db()
        try:
            existing_room = await db.scalar(select(Group).where(Group.name == room_id))
            if existing_room and room_id.startswith("dm_"):
                # Auto-add user as WRITE member if they're joining a DM that exists
                role = membership_service.auto_join_user_to_room(room_id, user_id)
            else:
                await websocket.accept()
                await websocket.send_json(
                    build_error_response(
                    room_id=room_id,
                    code="not_a_member",
                    message="User is not a member of this room",
                ))
                await websocket.close(code=1008)
                return
        except Exception as e:
            await websocket.accept()
            await websocket.send_json(
                build_error_response(
                room_id=room_id,
                code="error",
                message=f"Failed to join room: {str(e)}",
            ))
            await websocket.close(code=1008)
            return
        finally:
            await db.close()

    
    await websocket.accept()
    connection_manager.connect(room_id, websocket)
    await websocket.send_json({
        "event": "system.connected",
        "room_id": room_id,
        "payload": {"message": "WebSocket connected", "user_id": user_id},
    })

    try:
        while True:
            try: 
                raw_data = await websocket.receive_json()
                message = WsMessage.model_validate(raw_data)
            except ValidationError as e:
                await websocket.send_json(
                    build_error_response(
                        room_id=room_id,
                        code="invalid_payload",
                        message="Invalid message envelope",
                        details={"errors": e.errors()},
                    )
                )
                continue
            except ValueError:
                await websocket.send_json(
                    build_error_response(
                        room_id=room_id,
                        code="invalid_json",
                        message="Invalid JSON payload",
                    )
                )
                continue
            
            if message.room_id != room_id:
                await websocket.send_json(
                    build_error_response(
                        room_id=room_id,
                        code="room_mismatch",
                        message="Payload room_id must match websocket room_id",
                    )
                )
                continue
            
            response = await event_dispatch(message, user_id, websocket)
            if response is not None:
                await websocket.send_json(response)
    except WebSocketDisconnect:
        return 
    
    finally:
        try:
            await typing_service.stop_typing(room_id=room_id, user_id=user_id)
        except Exception:
            pass
        connection_manager.disconnect(room_id, websocket)

async def handle_message_send(data: WsMessage, user_id: str, sender_websocket: WebSocket | None = None) -> dict[str, Any] | None:
    role = get_user_role(data.room_id, user_id)

    #checks the role of the user 
    if not can_send_message(role):
        return build_error_response(
            room_id=data.room_id,
            code="forbidden",
            message="You do not have permission to send messages",
            details={"role": role.value if role else None}
        )

    payload = data.payload if isinstance(data.payload, dict) else {}
    text = payload.get("text")
    attachment_id = payload.get("attachment_id")
    
    # Exactly one of text or attachment_id must be present
    if text and attachment_id:
        return build_error_response(
            room_id=data.room_id,
            code="invalid_payload",
            message="Message must contain either text or attachment_id, not both"
        )
    
    if not text and not attachment_id:
        return build_error_response(
            room_id=data.room_id,
            code="invalid_payload",
            message="Message must contain either text or attachment_id"
        )
    
    db = await get_db()
    
    try:
        # TEXT MESSAGE PATH
        if text:
            if not isinstance(text, str) or not text.strip():
                return build_error_response(
                    room_id=data.room_id,
                    code="invalid_payload",
                    message="payload.text cannot be empty"
                )
            
            try:
                msg = await save_message(
                    db,
                    room_id=data.room_id,
                    sender_external_id=user_id,
                    text=text,
                    message_type=MessageType.TEXT,
                )
            except ValueError as e:
                return build_error_response(
                    room_id=data.room_id,
                    code="db_error",
                    message=f"Failed to save message: {str(e)}",
                )
            
            outgoing_message = {
                "event": "message.receive",
                "room_id": data.room_id,
                "payload": {
                    "message_id": msg.id,
                    "type": "text",
                    "text": text.strip(),
                    "user_id": user_id,
                    "created_at": msg.created_at.isoformat(),
                }
            }
            
            await connection_manager.broadcast(data.room_id, outgoing_message)
            return None
        
        # ATTACHMENT MESSAGE PATH
        if attachment_id:
            try:
                attachment = await attachment_service.get_attachment_by_id(db, attachment_id)
            except attachment_service.AttachmentNotFoundError:
                return build_error_response(
                    room_id=data.room_id,
                    code="invalid_payload",
                    message=f"Attachment {attachment_id} not found",
                )
            
            # Verify attachment belongs to this room
            if attachment.room_id != data.room_id:
                return build_error_response(
                    room_id=data.room_id,
                    code="forbidden",
                    message="Attachment does not belong to this room",
                )
            
            # Verify sender is the uploader
            if attachment.uploader_user_id != user_id:
                return build_error_response(
                    room_id=data.room_id,
                    code="forbidden",
                    message="Only the uploader can send this attachment",
                )
            
            # Verify attachment is still PENDING (not already used)
            from app.models.attachment import UploadStatus
            if attachment.upload_status != UploadStatus.PENDING:
                return build_error_response(
                    room_id=data.room_id,
                    code="conflict",
                    message="Attachment has already been used in another message",
                )
            
            # Confirm upload and save message
            try:
                await attachment_service.confirm_upload(db, attachment_id, user_id)
                
                msg = await save_message(
                    db,
                    room_id=data.room_id,
                    sender_external_id=user_id,
                    attachment_id=attachment_id,
                    message_type=MessageType.ATTACHMENT,
                )
            except Exception as e:
                return build_error_response(
                    room_id=data.room_id,
                    code="db_error",
                    message=f"Failed to process attachment: {str(e)}",
                )
            
            outgoing_message = {
                "event": "message.receive",
                "room_id": data.room_id,
                "payload": {
                    "message_id": msg.id,
                    "type": "attachment",
                    "user_id": user_id,
                    "attachment": {
                        "id": str(attachment.id),
                        "filename": attachment.filename,
                        "content_type": attachment.content_type,
                        "size_bytes": attachment.size_bytes,
                    },
                    "created_at": msg.created_at.isoformat(),
                }
            }
            
            await connection_manager.broadcast(data.room_id, outgoing_message, sender_websocket)
            return None
    finally:
        await db.close()


async def handle_typing_event(
    data: WsMessage,
    user_id: str,
    sender_websocket: WebSocket,
    is_typing: bool,
) -> dict[str, Any] | None:
    if not membership_service.is_room_member(data.room_id, user_id):
        return build_error_response(
            room_id=data.room_id,
            code="forbidden",
            message="User is not a member of this room",
        )

    if is_typing:
        await typing_service.start_typing(room_id=data.room_id, user_id=user_id)
    else:
        await typing_service.stop_typing(room_id=data.room_id, user_id=user_id)

    await connection_manager.broadcast(
        data.room_id,
        {
            "event": "typing.update",
            "room_id": data.room_id,
            "payload": {
                "user_id": user_id,
                "typing": is_typing,
            },
        },
        exclude=sender_websocket,
    )
    return None
    
async def event_dispatch(
    data: WsMessage,
    user_id: str,
    sender_websocket: WebSocket,
) -> dict[str, Any] | None:
    if data.event == "message.send":
        return await handle_message_send(data, user_id, sender_websocket)

    if data.event == "typing.start":
        return await handle_typing_event(data, user_id, sender_websocket, is_typing=True)

    if data.event == "typing.stop":
        return await handle_typing_event(data, user_id, sender_websocket, is_typing=False)

    return build_error_response(
        room_id=data.room_id,
        code="unsupported_event",
        message=f"Unsupported event: {data.event}",
    )


def build_error_response(
        *,
        room_id: str,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
        meta: dict[str, Any] | None = None
) -> dict[str, Any]:
    
    payload: dict[str, Any] = {
        "code": code,
        "message": message
    }

    if details is not None:
        payload["details"] = details

    response = {
        "event": "error",
        "room_id": room_id,
        "payload": payload
    }

    if meta is not None:
        response["meta"] = meta

    return response