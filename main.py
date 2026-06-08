import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.database import create_db_and_tables
from app.core.config import settings

# ── Importar todos los modelos para que SQLModel los registre ──────────────────
from app.core.links import ProductoCategoria, ProductoIngrediente  # noqa: F401
from app.modules.auth.model import Usuario, Rol, UsuarioRol, RefreshToken, PasswordResetToken  # noqa: F401
from app.modules.categorias.model import Categoria      # noqa: F401
from app.modules.ingredientes.model import Ingrediente  # noqa: F401
from app.modules.productos.model import Producto        # noqa: F401
from app.modules.direcciones.model import DireccionEntrega  # noqa: F401
from app.modules.pedidos.model import (                     # noqa: F401
    EstadoPedido, FormaPago, Pedido, DetallePedido, HistorialEstadoPedido,
)

# ── Routers ────────────────────────────────────────────────────────────────────
from app.modules.auth.router         import router as auth_router
from app.modules.categorias.router   import router as categorias_router
from app.modules.ingredientes.router import router as ingredientes_router
from app.modules.productos.router    import router as productos_router
from app.modules.direcciones.router  import router as direcciones_router
from app.modules.pedidos.router      import router as pedidos_router
from app.modules.admin.router        import router as admin_router   # ← NUEVO

limiter = Limiter(key_func=get_remote_address)


async def _auto_cancelar_loop():
    """Cancela pedidos ESPERANDO_PAGO sin pago confirmado cada 15 minutos."""
    while True:
        await asyncio.sleep(900)  # 15 min
        try:
            from app.core.unit_of_work import UnitOfWork
            from app.modules.pedidos import service as pedidos_service
            with UnitOfWork() as uow:
                cancelados = pedidos_service.cancelar_pedidos_expirados(uow)
            if cancelados:
                print(f"[AUTO-CANCEL] {cancelados} pedido(s) cancelado(s) por timeout de pago.")
        except Exception as e:
            print(f"[AUTO-CANCEL] Error en ciclo de cancelación: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    try:
        from app.db.seed import seed
        seed()
    except Exception as e:
        print(f"[SEED] Warning: {e}")
    task = asyncio.create_task(_auto_cancelar_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Food Store API",
    description="API REST — FastAPI + SQLModel + PostgreSQL · Arquitectura feature-first",
    version="3.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": "Error interno del servidor", "code": "INTERNAL_ERROR"},
    )


# Registrar routers
app.include_router(auth_router)
app.include_router(categorias_router)
app.include_router(ingredientes_router)
app.include_router(productos_router)
app.include_router(direcciones_router)
app.include_router(pedidos_router)
app.include_router(admin_router)


@app.get("/", tags=["Root"])
def root():
    return {"mensaje": "Food Store API v3 — feature-first"}


@app.get("/debug/ws-rooms", tags=["debug"])
def ws_rooms():
    """Rooms WebSocket activas y cantidad de sockets por room."""
    from app.core.websocket import manager
    return {
        "total_connections": manager.get_active_connections_count(),
        "rooms": manager.get_rooms_info(),
    }