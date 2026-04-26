# Parcial 1 — Programación IV


Aplicación Fullstack de gestión de productos gastronómicos con categorías e ingredientes. Desarrollada con **FastAPI + SQLModel** en el backend y **React + TypeScript + TanStack Query** en el frontend.


---

## Tecnologías

### Backend
- **Python 3.12+**
- **FastAPI** — framework web moderno y de alto rendimiento
- **SQLModel** — ORM con tipado estático (SQLAlchemy + Pydantic)
- **PostgreSQL** — base de datos relacional
- **Uvicorn** — servidor ASGI
- **python-dotenv** — variables de entorno

### Frontend
- **React 19 + TypeScript**
- **Vite 6** — bundler
- **TanStack Query v5** — server state management
- **React Router DOM v7** — navegación SPA
- **Tailwind CSS 4** — estilos utilitarios

---

## Estructura del Proyecto

```
PArcial 1/
├── backend/                  # API REST
│   ├── main.py               # Entry point + CORS + lifespan
│   ├── requirements.txt
│   ├── .env                  # DATABASE_URL (no versionado)
│   └── app/
│       ├── models/           # SQLModel - tablas DB con relaciones N:N
│       │   ├── links.py      # ProductoCategoria, ProductoIngrediente
│       │   ├── categoria.py
│       │   ├── ingrediente.py
│       │   └── producto.py
│       ├── schemas/          # Pydantic - contratos de entrada/salida
│       ├── services/         # Lógica de negocio
│       ├── routers/          # Endpoints HTTP con Annotated, Query, Path
│       └── uow/              # Unit of Work (manejo de transacciones)
│
└── frontend/                 # SPA React
    ├── src/
    │   ├── pages/            # CategoriasPage, IngredientesPage, ProductosPage, ProductoDetallePage
    │   ├── components/       # Layout, Modal
    │   ├── services/         # api.ts (cliente HTTP tipado)
    │   └── types/            # Interfaces TypeScript
    └── vite.config.ts
```

---

## Modelo de Datos

```
Categoria ──── ProductoCategoria ──── Producto ──── ProductoIngrediente ──── Ingrediente
              (N:N)                               (N:N con cantidad)
```

---

## Cómo ejecutar

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt

# Crear archivo .env con:
# DATABASE_URL=postgresql://postgres:TU_CONTRASEÑA@localhost:5432/parcial1_db

uvicorn main:app --reload
```

API disponible en: `http://localhost:8000`  
Swagger UI: `http://localhost:8000/docs`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

App disponible en: `http://localhost:5173`

> ⚠️ El backend debe estar corriendo antes de iniciar el frontend.

---

## Endpoints principales

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/categorias/` | Listar con filtros y paginación |
| POST | `/categorias/` | Crear categoría |
| PUT | `/categorias/{id}` | Actualizar categoría |
| DELETE | `/categorias/{id}` | Eliminar categoría |
| GET | `/ingredientes/` | Listar con filtros y paginación |
| POST | `/ingredientes/` | Crear ingrediente |
| GET | `/productos/` | Listar con filtros (nombre, precio, categoría) |
| GET | `/productos/{id}` | Detalle con categorías e ingredientes |
| POST | `/productos/` | Crear con categorías e ingredientes |
| PUT | `/productos/{id}` | Actualizar producto |
| DELETE | `/productos/{id}` | Eliminar producto |

---
