from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import create_db_and_tables

# Importar modelos para que SQLModel los registre en el metadata ANTES de crear las tablas
from app.models import Categoria, Ingrediente, Producto, ProductoCategoria, ProductoIngrediente  # noqa: F401

from app.routers.categorias import router as categorias_router
from app.routers.ingredientes import router as ingredientes_router
from app.routers.productos import router as productos_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Crea las tablas en la DB al iniciar la aplicación."""
    create_db_and_tables()
    yield


app = FastAPI(
    title="Parcial 1 - Programación IV",
    description="API REST fullstack con FastAPI + SQLModel + PostgreSQL",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS para permitir requests desde el frontend React
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar routers
app.include_router(categorias_router)
app.include_router(ingredientes_router)
app.include_router(productos_router)


@app.get("/", tags=["Root"])
def root():
    return {"mensaje": "API Parcial 1 - Programación IV funcionando 🚀"}
