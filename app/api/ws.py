from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Any
from app.schemas.events import WsMessage
from pydantic import ValidationError
from app.models.membership import GroupRole
from app.services.authorization import can_send_message
router = APIRouter()

TEMP_SERVER_ROLE = GroupRole.WRITE

@router.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str) -> None:
    await websocket.accept()
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
            await websocket.send_json(response)
    except WebSocketDisconnect:
        return 
    
    finally:
        await websocket.close()

async def handle_message_send(data: WsMessage) -> dict[str, Any]:
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

    return {
            "event": "message.receive",
            "room_id": data.room_id,
            "payload": {
                "text": text.strip()
            }
        }
    
async def event_dispatch(data: WsMessage) -> dict[str, Any]:
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
    
