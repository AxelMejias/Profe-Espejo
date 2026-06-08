import logging
from typing import Any
from fastapi import WebSocket

logger = logging.getLogger("app.core.websocket")


class ConnectionManager:
    """
    Gestor de conexiones WebSocket con rooms por rol y por pedido.

    Mantiene dos estructuras en espejo:
      rooms:        room_name → set de WebSockets en esa room
      socket_rooms: WebSocket → set de rooms donde está ese socket

    El espejo permite limpiar todas las rooms de un socket en O(1) al desconectar.
    """

    def __init__(self) -> None:
        self.rooms: dict[str, set[WebSocket]] = {}
        self.socket_rooms: dict[WebSocket, set[str]] = {}

    async def connect(self, websocket: WebSocket, role: str, user_id: int) -> None:
        await websocket.accept()
        self._join_room(websocket, f"role:{role.lower()}")
        logger.info(f"WS conectado user_id={user_id} role={role} rooms_activas={len(self.rooms)}")

    def disconnect(self, websocket: WebSocket) -> None:
        rooms = self.socket_rooms.pop(websocket, set())
        for room in rooms:
            if room in self.rooms:
                self.rooms[room].discard(websocket)
                if not self.rooms[room]:
                    del self.rooms[room]
        logger.info(f"WS desconectado. Rooms liberadas: {rooms}")

    def join_order_room(self, websocket: WebSocket, order_id: int) -> None:
        self._join_room(websocket, f"order:{order_id}")

    def leave_order_room(self, websocket: WebSocket, order_id: int) -> None:
        room = f"order:{order_id}"
        if room in self.rooms:
            self.rooms[room].discard(websocket)
        if websocket in self.socket_rooms:
            self.socket_rooms[websocket].discard(room)
        if room in self.rooms and not self.rooms[room]:
            del self.rooms[room]

    async def broadcast_to_order(self, order_id: int, event_type: str, data: dict[str, Any]) -> None:
        await self._emit_to_room(f"order:{order_id}", event_type, data)

    async def broadcast_to_role(self, role: str, event_type: str, data: dict[str, Any]) -> None:
        await self._emit_to_room(f"role:{role.lower()}", event_type, data)

    async def broadcast_to_roles(
        self, roles: list[str], event_type: str, data: dict[str, Any]
    ) -> None:
        """Envía a múltiples rooms de rol sin duplicar envíos a sockets en varias rooms."""
        sent_to: set[WebSocket] = set()
        payload = {"event": event_type, "data": data}
        for role in roles:
            room = f"role:{role.lower()}"
            if room not in self.rooms:
                continue
            for conn in list(self.rooms[room]):
                if conn not in sent_to:
                    try:
                        await conn.send_json(payload)
                        sent_to.add(conn)
                    except Exception as e:
                        logger.warning(f"Error WS send, removiendo conexión: {e}")
                        self.disconnect(conn)

    def get_active_connections_count(self) -> int:
        return len(self.socket_rooms)

    def get_rooms_info(self) -> dict[str, int]:
        return {room: len(sockets) for room, sockets in self.rooms.items()}

    def _join_room(self, websocket: WebSocket, room: str) -> None:
        self.rooms.setdefault(room, set()).add(websocket)
        self.socket_rooms.setdefault(websocket, set()).add(room)

    async def _emit_to_room(self, room: str, event_type: str, data: dict[str, Any]) -> None:
        if room not in self.rooms:
            return
        payload = {"event": event_type, "data": data}
        for conn in list(self.rooms[room]):
            try:
                await conn.send_json(payload)
            except Exception as e:
                logger.warning(f"Error WS send, removiendo conexión: {e}")
                self.disconnect(conn)


manager = ConnectionManager()
