from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Any
from app.schemas.events import WsMessage
from pydantic import ValidationError
from app.services.authorization import can_send_message
from app.services.membership import get_user_role
from app.realtime.connection_manager import ConnectionManager
from app.db.session import get_db
from app.services.message_service import save_message
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
    if role is None:
        await websocket.accept()
        await websocket.send_json(
            build_error_response(
            room_id=room_id,
            code="not_a_member",
            message="User is not a member of this room",
        ))
        await websocket.close(code=1008)
        return

    
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
            
            response = await event_dispatch(message, user_id)
            if response is not None:
                await websocket.send_json(response)
    except WebSocketDisconnect:
        return 
    
    finally:
        connection_manager.disconnect(room_id, websocket)

async def handle_message_send(data: WsMessage, user_id: str) -> dict[str, Any] | None:
    role = get_user_role(data.room_id, user_id)

    #checks the role of the user 
    if not can_send_message(role):
        return build_error_response(
            room_id=data.room_id,
            code="forbidden",
            message="You do not have permission to send messages",
            details={"role": role.value}
        )

    text = data.payload.get("text") if isinstance(data.payload, dict) else None

    #trying to send empty message
    if not isinstance(text, str) or not text.strip():
        return build_error_response(
            room_id=data.room_id,
            code="invalid_payload",
            message="payload.text is required and cannot be empty"
        )
    
    db = await get_db()
    try:
        msg = await save_message(db, room_id=data.room_id, 
                                sender_external_id=user_id,
                                text=text
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
            "text": text.strip(),
            "user_id": user_id,
            "created_at": msg.created_at.isoformat(),
        }
    }

    #sending message to users in the specific room
    await connection_manager.broadcast(data.room_id, outgoing_message)
    return None
    
async def event_dispatch(data: WsMessage, user_id: str) -> dict[str, Any] | None:
    if data.event == "message.send":
        return await handle_message_send(data, user_id)

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