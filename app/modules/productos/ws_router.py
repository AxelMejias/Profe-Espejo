"""
Endpoint WebSocket PÚBLICO del catálogo.

  • ws://<host>/ws/catalogo  → canal de la tienda. Sin autenticación: cualquier
    visitante (anónimo o cliente) recibe los eventos de catálogo
    (productos/ingredientes) para refrescar la tienda en vivo, igual que el panel
    admin con /ws/admin/pedidos.

Formato de evento (ver app/core/websocket.emit_catalogo_evento):
  {event, timestamp, ...ids}
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.websocket import manager

router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws/catalogo")
async def ws_catalogo(websocket: WebSocket):
    """Canal público del catálogo: solo recibe avisos de cambio (no envía datos
    sensibles); la tienda invalida sus queries y vuelve a pedir el catálogo por REST."""
    await websocket.accept()
    manager.join_catalogo_publico(websocket)
    try:
        # El cliente solo escucha; mantenemos viva la conexión.
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
