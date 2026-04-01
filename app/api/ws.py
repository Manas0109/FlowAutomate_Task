from fastapi import APIRouter, WebSocket

router = APIRouter()


@router.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str) -> None:
    await websocket.accept()
    await websocket.send_json({
        "event": "system.connected",
        "room_id": room_id,
        "message": "WebSocket connected",
    })

    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(data)
    except Exception:
        await websocket.close()
