# FlowAutomate Task - Chat Backend Scaffold

Backend scaffold for a FastAPI + WebSocket based chat system.

## Delivery Scope (Current)

- **Step 1 (now):** One-to-one (direct) chat communication.
- **Step 2 (next):** Group chat communication using the same envelope/event foundation.

## Glossary (Phase 0)

- **Room**: Logical chat channel identified by `room_id` (can represent a direct 1:1 conversation first, then group channels).
- **Member**: User connected to a room.
- **Membership Role**: Permission level in a group (`ADMIN`, `WRITE`, `READ`).
- **Message**: Chat payload sent by a client and broadcast to room members.
- **Receipt**: Read-state signal for messages (planned in later phase).
- **Presence / Typing State**: Ephemeral activity signal such as `typing.start` and `typing.stop`.
- **Attachment**: Metadata reference to media/document stored in object storage.

## Event Contract v1 (Frozen)

The minimal event set for the first chat milestone is locked as:

- `message.send` (client -> server)
- `message.receive` (server -> room clients)
- `error` (server -> client)

All WebSocket traffic should follow a structured envelope:

- `event`: event name
- `room_id`: room identifier
- `payload`: event-specific data
- `meta`: optional metadata (timestamps/correlation later)

## Done Criteria

### MVP Done

- Two clients connected to the same **direct-chat room** can exchange messages in realtime.
- Server accepts `message.send` and broadcasts `message.receive` consistently.
- Invalid payloads return a standard `error` envelope.
- Socket disconnect cleans up room connection state correctly.

### Production-Ready Done

- JWT-based identity and role enforcement are active.
- Messages and memberships are persisted in PostgreSQL.
- Multi-instance fan-out works through Redis Pub/Sub.
- Typing state works via Redis TTL and remains ephemeral.
- Attachment upload flow uses object storage + DB metadata.
- Test coverage exists for unit and integration chat flows.
- Runtime protections are in place (rate limits, payload limits, structured logs).

## Project Structure

```text
.
├── app/
│   ├── api/
│   │   ├── routes.py              # API router registration
│   │   └── ws.py                  # WebSocket endpoint(s)
│   ├── core/
│   │   └── config.py              # App settings/config
│   ├── db/                        # Database layer placeholders
│   ├── models/
│   │   └── membership.py          # Group role enums (ADMIN/WRITE/READ)
│   ├── realtime/
│   │   └── connection_manager.py  # Connection manager placeholder
│   ├── repositories/              # Data access placeholders
│   ├── schemas/
│   │   └── events.py              # WebSocket envelope schema
│   ├── services/
│   │   └── authorization.py       # Role-based permission checks
│   └── main.py                    # FastAPI app factory
├── alembic/
│   └── versions/                  # Migration versions
├── tests/                         # Test package
├── main.py                        # Local run entrypoint (uvicorn)
└── pyproject.toml                 # Project + dependency config
```

## Run

```bash
uv run python main.py
```
