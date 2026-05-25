# 🍔 Food Store — Backend API

API REST construida con **FastAPI + SQLModel + PostgreSQL** siguiendo una arquitectura **feature-first** con capas estrictas.

## Repositorios del proyecto

Este proyecto sigue una arquitectura **polyrepo**: cada capa tiene su propio repositorio independiente.

| Capa | Repositorio | Rama |
|---|---|---|
| 🔧 Backend (este repo) | [AxelMejias/Profe-Espejo](https://github.com/AxelMejias/Profe-Espejo) | `FoodStoreBack` |
| 🌐 Frontend | [AxelMejias/Prgo-4-Magni](https://github.com/AxelMejias/Prgo-4-Magni) | `Integrador` |

---

## Stack tecnológico

| Capa | Tecnología |
|---|---|
| Framework | FastAPI 0.100+ |
| ORM | SQLModel (SQLAlchemy + Pydantic v2) |
| Base de datos | PostgreSQL 15 |
| Migraciones | Alembic |
| Autenticación | JWT (access 30 min) + Refresh Token (7 días) + Cookie HTTPOnly |
| Hash contraseñas | bcrypt (cost factor 12) |
| Rate limiting | slowapi |
| Export Excel | openpyxl |
| OAuth social | Google OAuth 2.0 |

---

## Arquitectura

```
Router → Service → UnitOfWork → Repository → Model
```

Cada módulo tiene sus propios archivos `model.py`, `schemas.py`, `repository.py`, `service.py` y `router.py`. Ninguna capa importa de una capa superior.

### Patrones aplicados

| Patrón | Descripción |
|---|---|
| Unit of Work | Commit/rollback atómico. El Service nunca llama a `session.commit()` directamente |
| Repository Pattern | `BaseRepository[T]` genérico con CRUD base; cada módulo extiende con sus queries |
| Service Layer | Lógica de negocio stateless. Nunca en el router |
| Soft Delete | `deleted_at TIMESTAMPTZ` en todas las entidades de negocio |
| Snapshot Pattern | Precio y nombre inmutables en `DetallePedido` |
| Audit Trail Append-Only | `HistorialEstadoPedido` solo permite INSERTs |

---

## Requisitos previos

| Herramienta | Versión mínima |
|---|---|
| Python | 3.11+ |
| PostgreSQL | 15+ |

---

## Instalación y setup

### 1. Clonar el repositorio

```bash
git clone https://github.com/AxelMejias/Profe-Espejo.git
cd Profe-Espejo
```

### 2. Crear la base de datos

En pgAdmin o psql:

```sql
CREATE DATABASE foodstore_db;
```

### 3. Crear y activar el entorno virtual

```bash
# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1

# Mac / Linux
python -m venv .venv
source .venv/bin/activate
```

### 4. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 5. Configurar la base de datos

Editá `app/core/config.py` y cambiá la contraseña de PostgreSQL:

```python
DATABASE_URL: str = "postgresql://postgres:TU_CONTRASEÑA@localhost:5432/foodstore_db"
```

### 6. Correr migraciones

```bash
alembic upgrade head
```

### 7. Iniciar el servidor

```bash
uvicorn main:app --reload
```

El seed (roles, estados, formas de pago y cuentas de staff) se ejecuta **automáticamente** al iniciar el servidor.

El backend queda disponible en:
- API: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## Credenciales de acceso por defecto

| Rol | Email | Contraseña |
|---|---|---|
| Administrador | admin@foodstore.com | Admin1234! |
| Gestor de Pedidos (Cocina) | cocina@foodstore.com | Cocina1234! |
| Gestor de Stock | stock@foodstore.com | Stock1234! |

> Los usuarios que se registran desde el frontend reciben el rol `CLIENT` automáticamente.
> Las tres cuentas de staff se crean automáticamente al correr el seed (idempotente).

---

## Módulos implementados

### Autenticación (`/api/v1/auth/`)

| Método | Endpoint | Descripción |
|---|---|---|
| POST | `/register` | Registro con asignación automática del rol CLIENT |
| POST | `/login` | Login email/password → JWT + cookie HTTPOnly |
| POST | `/refresh` | Renueva el access token (rotación de refresh token) |
| POST | `/logout` | Revoca el refresh token y limpia la cookie |
| GET | `/me` | Datos del usuario autenticado |
| POST | `/google` | Login con Google OAuth 2.0 |
| POST | `/forgot-password` | Solicitud de reset de contraseña |
| POST | `/reset-password` | Aplicar nueva contraseña con token |

### Roles del sistema (RBAC)

| Rol | Código | Capacidades |
|---|---|---|
| Administrador | `ADMIN` | CRUD completo de todo el sistema |
| Gestor de Stock | `STOCK` | Leer productos, actualizar stock y disponibilidad |
| Gestor de Pedidos | `PEDIDOS` | Ver y avanzar estados de pedidos |
| Cliente | `CLIENT` | Catálogo, carrito, pedidos propios |

### Catálogo — Categorías (`/api/v1/categorias/`)

- CRUD completo (solo ADMIN)
- Categorías jerárquicas con autorreferencia (`parent_id`)
- Soft delete con validación: 409 si tiene productos activos
- Listado público con filtro por nombre y paginación

### Catálogo — Ingredientes (`/api/v1/ingredientes/`)

- CRUD completo (ADMIN / STOCK)
- Campo `es_alergeno` con badge visual en el frontend
- Export a Excel (`GET /exportar`)
- Filtros por nombre, unidad de medida y alérgeno

### Catálogo — Productos (`/api/v1/productos/`)

- CRUD completo (ADMIN / STOCK)
- Filtros: categoría, disponibilidad, búsqueda por texto, paginación
- Gestión de ingredientes asociados con campo `es_alergeno`
- `PATCH /disponibilidad` para activar/desactivar (ADMIN y STOCK)
- Campos `stock_cantidad` y `disponible` independientes
- Soft delete

### Pedidos (`/api/v1/pedidos/`)

- Creación desde el carrito con transacción atómica (Unit of Work)
- Máquina de estados de 6 estados:

```
PENDIENTE → CONFIRMADO → EN_PREP → EN_CAMINO → ENTREGADO
         ↘            ↘         ↘
                          CANCELADO
```

- Avance de estado validado en la capa de servicio (nunca en el router)
- Audit Trail append-only: `HistorialEstadoPedido` con solo INSERTs
- Snapshot Pattern: precio y nombre del producto inmutables al crear el pedido
- CLIENT ve solo sus pedidos; ADMIN/PEDIDOS ven todos
- Cancelación por el cliente solo desde PENDIENTE o CONFIRMADO

### Direcciones de Entrega (`/api/v1/direcciones/`)

- CRUD completo para el usuario autenticado
- `PATCH /principal` para marcar una dirección como principal (una por usuario)
- Soft delete
- Campo `alias` (ej: "Casa", "Trabajo")

### Panel de Administración (`/api/v1/admin/`)

- Listado paginado de usuarios con filtro por rol
- Actualización de datos de usuario
- Soft delete de usuarios
- Asignación y remoción de roles

---

## Seguridad

- **Cookie HTTPOnly**: el access token se setea como cookie HTTPOnly en login/refresh y se limpia en logout
- **Estrategia dual**: el backend acepta JWT desde cookie HTTPOnly o desde header `Authorization: Bearer` (compatible con ambos módulos frontend)
- **bcrypt**: hash de contraseñas con cost factor ≥ 12
- **JWT**: access token (30 min) + refresh token con rotación (7 días)
- **Rate limiting**: 60 intentos de login cada 15 minutos por IP
- **CORS**: configurado con `allow_credentials=True`
- **Soft Delete**: ninguna entidad se elimina físicamente

---

## Estructura del proyecto

```
Profe-Espejo/
├── main.py                      # Entry point FastAPI + lifespan (seed auto-run)
├── requirements.txt
├── alembic/                     # Migraciones de base de datos
│   └── versions/
└── app/
    ├── core/                    # Infraestructura compartida
    │   ├── config.py            # Settings (DATABASE_URL, SECRET_KEY, cookies…)
    │   ├── database.py          # Engine + create_db_and_tables
    │   ├── security.py          # hash_password, create_access_token, decode…
    │   ├── dependencies.py      # get_current_user, require_role (cookie + Bearer)
    │   ├── links.py             # Tablas pivot N:N (ProductoCategoria, ProductoIngrediente)
    │   ├── base_repository.py   # BaseRepository[T] genérico
    │   └── unit_of_work.py      # UnitOfWork con commit/rollback automático
    ├── db/
    │   └── seed.py              # Datos iniciales (idempotente)
    └── modules/                 # Arquitectura feature-first
        ├── auth/                # Login, registro, JWT, Google OAuth
        ├── categorias/          # CRUD categorías jerárquicas
        ├── ingredientes/        # CRUD ingredientes + export Excel
        ├── productos/           # CRUD productos con stock
        ├── pedidos/             # FSM de pedidos + audit trail
        ├── direcciones/         # Direcciones de entrega
        └── admin/               # Gestión de usuarios y roles
```

---

## Variables de configuración

Editables en `app/core/config.py` o mediante un archivo `.env`:

| Variable | Descripción | Default |
|---|---|---|
| `DATABASE_URL` | Cadena de conexión PostgreSQL | `postgresql://postgres:postgres@localhost:5432/foodstore_db` |
| `SECRET_KEY` | Clave para firmar JWT (mín. 32 chars) | — |
| `ALGORITHM` | Algoritmo JWT | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Duración del access token | `30` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Duración del refresh token | `7` |
| `CORS_ORIGINS` | Orígenes permitidos | `["http://localhost:5173"]` |
| `COOKIE_SECURE` | Cookie solo en HTTPS (producción) | `False` |
| `COOKIE_SAMESITE` | Política SameSite de la cookie | `lax` |

---

## Tests

El proyecto usa **pytest** con mocks (sin base de datos real). Los servicios reciben el `UnitOfWork` como parámetro, lo que los hace completamente testeables de forma aislada.

### Cobertura

| Archivo de test | Módulo | Tests |
|---|---|---|
| `test_security.py` | `app/core/security.py` | hash, verify, JWT encode/decode |
| `test_auth_service.py` | `app/modules/auth/service.py` | login, registro, webhook n8n |
| `test_admin_service.py` | `app/modules/admin/service.py` | CRUD usuarios + asignar/remover rol |
| `test_categorias_service.py` | `app/modules/categorias/service.py` | CRUD + subcategorías + conflictos |
| `test_ingredientes_service.py` | `app/modules/ingredientes/service.py` | CRUD + alérgenos + conflictos |
| `test_productos_service.py` | `app/modules/productos/service.py` | CRUD + categorías/ingredientes + disponibilidad + reactivar |
| `test_direcciones_service.py` | `app/modules/direcciones/service.py` | CRUD + marcar principal + ownership |
| `test_pedidos_service.py` | `app/modules/pedidos/service.py` | crear pedido + FSM de estados + RBAC |

### Correr los tests

```bash
# Activar entorno virtual primero
.venv\Scripts\Activate.ps1          # Windows
source .venv/bin/activate           # Mac / Linux

# Correr todos los tests
pytest

# Con output detallado
pytest -v

# Un módulo específico
pytest tests/test_productos_service.py -v

# Con reporte de cobertura
pytest --cov=app --cov-report=term-missing
```

---

## Comandos de referencia rápida

```bash
# Activar entorno virtual (Windows)
.venv\Scripts\Activate.ps1

# Iniciar servidor
uvicorn main:app --reload

# Correr migraciones
alembic upgrade head

# Ver estado de migraciones
alembic current

# Generar nueva migración
alembic revision --autogenerate -m "descripcion"
```

---

## Changelog

### 24/05/2026 — Parcial 2

**Bug fixes**

| Archivo | Problema | Fix |
|---|---|---|
| `core/unit_of_work.py` | `uow.usuarios_admin` importaba el stub vacío de `modules/usuarios/repository.py` — todos los endpoints de `/api/v1/admin/usuarios` fallaban con `AttributeError` | Cambiada importación a `modules/admin/repository.py` donde está la implementación real |
| `modules/pedidos/service.py` | `costo_envio` siempre era `$50` sin importar si el pedido era retiro o envío a domicilio | Ahora es `$0` cuando `direccion_id is None` (retiro en local) y `$50` solo cuando tiene dirección de entrega |
| `modules/auth/router.py` | Rate limit de `5/15min` bloqueaba al mismo desarrollador al probar múltiples cuentas desde la misma IP | Aumentado a `60/15min` |

**Nuevas funcionalidades**

- `modules/admin/`: el panel de administración de usuarios ya estaba implementado en el backend (endpoints `GET/PUT/DELETE /api/v1/admin/usuarios`, `POST/DELETE /api/v1/admin/usuarios/{id}/roles`) pero la importación rota en el UoW los dejaba inutilizables — con el fix del UoW quedaron completamente operativos

**Seed actualizado** (`app/db/seed.py`)

- Agregadas funciones `_seed_cocina()` y `_seed_stock()` — crean automáticamente las cuentas de staff al iniciar el proyecto por primera vez
- Corregida descripción de forma de pago: `"Efectivo (retiro en local)"` → `"Efectivo"`
- El seed es completamente idempotente: si las cuentas ya existen no hace nada ni tira error
