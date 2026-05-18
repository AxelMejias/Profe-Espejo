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
# Tablas pivot compartidas (deben importarse antes que los modelos que las usan)
from app.core.links import ProductoCategoria, ProductoIngrediente  # noqa: F401

# Módulo auth
from app.modules.auth.model import Usuario, Rol, UsuarioRol, RefreshToken, PasswordResetToken  # noqa: F401

# Módulos de catálogo
from app.modules.categorias.model import Categoria      # noqa: F401
from app.modules.ingredientes.model import Ingrediente  # noqa: F401
from app.modules.productos.model import Producto        # noqa: F401

# ── Routers ────────────────────────────────────────────────────────────────────
from app.modules.auth.router       import router as auth_router
from app.modules.categorias.router  import router as categorias_router
from app.modules.ingredientes.router import router as ingredientes_router
from app.modules.productos.router   import router as productos_router

# Stubs (sin endpoints por ahora)
# from app.modules.pedidos.router    import router as pedidos_router
# from app.modules.pagos.router      import router as pagos_router
# from app.modules.direcciones.router import router as direcciones_router
# from app.modules.admin.router      import router as admin_router
# from app.modules.usuarios.router   import router as usuarios_router

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


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


@app.get("/", tags=["Root"])
def root():
    return {"mensaje": "Food Store API v3 — feature-first"}
