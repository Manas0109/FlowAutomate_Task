from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Any
from app.schemas.events import WsMessage
from pydantic import ValidationError
from app.models.membership import GroupRole
from app.services.authorization import can_send_message
from app.realtime.connection_manager import ConnectionManager

router = APIRouter()

TEMP_SERVER_ROLE = GroupRole.WRITE
connection_manager = ConnectionManager()

@router.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str) -> None:
    await websocket.accept()
    connection_manager.connect(room_id, websocket)
    await websocket.send_json({
        "event": "system.connected",
        "room_id": room_id,
        "payload": {"message": "WebSocket connected"},
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
                        code="invalid_envelope",
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
            
            response = await event_dispatch(message)
            if response is not None:
                await websocket.send_json(response)
    except WebSocketDisconnect:
        return 
    
    finally:
        connection_manager.disconnect(room_id, websocket)

async def handle_message_send(data: WsMessage) -> dict[str, Any] | None:
    if not can_send_message(TEMP_SERVER_ROLE):
        return build_error_response(
            room_id=data.room_id,
            code="forbidden",
            message="You do not have permission to send messages",
            details={"role": TEMP_SERVER_ROLE.value}
        )

    text = data.payload.get("text") if isinstance(data.payload, dict) else None

    if not isinstance(text,str) or not text.strip():
        return build_error_response(
            room_id=data.room_id,
            code="invalid_payload",
            message="payload.text is required and cannot be empty"
        )

    outgoing_message = {
        "event": "message.receive",
        "room_id": data.room_id,
        "payload": {
            "text": text.strip()
        }
    }

    await connection_manager.broadcast(data.room_id, outgoing_message)
    return None
    
async def event_dispatch(data: WsMessage) -> dict[str, Any] | None:
    if data.event == "message.send":
        return await handle_message_send(data)

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
    
