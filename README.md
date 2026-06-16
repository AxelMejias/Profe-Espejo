# 🍔 Food Store — Backend API

API REST construida con **FastAPI + SQLModel + PostgreSQL** siguiendo una arquitectura **feature-first** con capas estrictas (Router → Service → UnitOfWork → Repository → Model).

## Repositorios del proyecto

Arquitectura **polyrepo**: backend y frontend en repositorios separados.

| Capa | Repositorio | Rama |
|---|---|---|
| 🔧 Backend (este repo) | [AxelMejias/Profe-Espejo](https://github.com/AxelMejias/Profe-Espejo) | `FoodStoreBack` |
| 🌐 Frontend | [AxelMejias/Prgo-4-Magni](https://github.com/AxelMejias/Prgo-4-Magni) | `Integrador` |

🎥 **Video demostración https://www.youtube.com/watch?v=ymQGzmx5ZYk

---

## Stack tecnológico

| Capa | Tecnología |
|---|---|
| Framework | FastAPI |
| ORM | SQLModel (SQLAlchemy + Pydantic v2) |
| Base de datos | PostgreSQL 15+ |
| Migraciones | Alembic |
| Autenticación | JWT (access 30 min) + Refresh Token (7 días) + Cookie HTTPOnly |
| Hash contraseñas | bcrypt (cost factor 12) |
| Rate limiting | slowapi (5 intentos / 15 min en login y register) |
| Pagos | MercadoPago Checkout PRO + Webhook IPN |
| Imágenes | Cloudinary |
| Tiempo real | WebSocket nativo de FastAPI |
| Export/Import | openpyxl (Excel) |
| OAuth social | Google OAuth 2.0 |

---

## Arquitectura

```
Router → Service → UnitOfWork → Repository → Model
```

Cada módulo tiene `model.py`, `schemas.py`, `repository.py`, `service.py` y `router.py`. Ninguna capa importa de una capa superior.

| Patrón | Descripción |
|---|---|
| Unit of Work | Commit/rollback atómico. El Service nunca llama a `session.commit()` directamente |
| Repository Pattern | `BaseRepository[T]` genérico con CRUD base; cada módulo extiende con sus queries |
| Service Layer | Lógica de negocio stateless, independiente del framework |
| Soft Delete | `deleted_at` en las entidades de negocio |
| Snapshot Pattern | Precio y nombre inmutables en `DetallePedido` |
| Audit Trail append-only | `HistorialEstadoPedido` solo permite INSERTs |

---

## Requisitos previos

| Herramienta | Versión |
|---|---|
| Python | 3.11+ |
| PostgreSQL | 15+ |
| ngrok | _opcional_ — solo para el webhook IPN de MercadoPago |

---

## 🚀 Setup paso a paso

> El proyecto corre **completo sin configurar MercadoPago, Cloudinary ni ngrok**. Esos servicios son opcionales (ver más abajo). Con la configuración mínima se puede usar toda la tienda pagando con **Efectivo** o **Transferencia**.

### 1. Clonar el repositorio

```bash
git clone https://github.com/AxelMejias/Profe-Espejo.git
cd Profe-Espejo
git checkout FoodStoreBack
```

### 2. Crear el entorno virtual e instalar dependencias

```bash
# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1

# Mac / Linux
python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Crear la base de datos

En pgAdmin o psql:

```sql
CREATE DATABASE foodstore_db;
```

### 4. Configurar variables de entorno

Copiá `.env.example` a `.env` y ajustá al menos la cadena de conexión (usuario/contraseña de tu PostgreSQL):

```bash
cp .env.example .env
```

```dotenv
DATABASE_URL=postgresql://postgres:TU_CONTRASEÑA@localhost:5432/foodstore_db
SECRET_KEY=una-clave-secreta-de-al-menos-32-caracteres
```

> El resto de las variables (MercadoPago, Cloudinary, Google) tienen valores de ejemplo y **no son necesarias para levantar el proyecto**. Ver la sección [MercadoPago](#-mercadopago-checkout-pro) si querés probar pagos.

### 5. Correr las migraciones

```bash
alembic upgrade head
```

### 6. Cargar los datos iniciales (seed)

```bash
python -m app.db.seed
```

> El seed también se ejecuta **automáticamente** al iniciar el servidor (es idempotente: si los datos ya existen, no los duplica).

### 7. Iniciar el servidor

```bash
uvicorn main:app --reload
```

Disponible en:
- API: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## Datos que carga el seed (`app/db/seed.py`)

- **Roles:** ADMIN, STOCK, PEDIDOS, CLIENT
- **Estados de pedido (FSM v7, 5 estados):** PENDIENTE, CONFIRMADO, EN_PREP, ENTREGADO, CANCELADO
- **Formas de pago:** EFECTIVO, TRANSFERENCIA, MERCADOPAGO
- **Unidades de medida:** kg, g, L, ml, ud, porciones
- **Usuarios** (ver tabla abajo)
- **Catálogo:** 9 categorías jerárquicas, 26 insumos con stock y 10 productos con imágenes (Cloudinary)

### Credenciales sembradas

| Rol | Email | Contraseña |
|---|---|---|
| Administrador | `admin@foodstore.com` | `Admin1234!` |
| Gestor de Pedidos (Cocina) | `cocina@foodstore.com` | `Cocina1234!` |
| Gestor de Stock | `stock@foodstore.com` | `Stock1234!` |
| **Cliente (demo)** | `cliente@foodstore.com` | `Cliente1234!` |

> La cuenta de **cliente demo** permite probar la tienda sin registrarse ni usar Google. Los usuarios que se registran desde el frontend reciben el rol `CLIENT` automáticamente.

---

## 💳 MercadoPago (Checkout PRO)

El flujo de pago usa **Checkout PRO (redirect)**: se crea una preferencia, se redirige al checkout de MercadoPago, y al volver el pedido se confirma.

### Para probar pagos
1. Cargá un `MP_ACCESS_TOKEN` de **prueba (sandbox)** en el `.env` (panel de MercadoPago → *Tus integraciones*).
2. Pagá con una [tarjeta de prueba de MercadoPago](https://www.mercadopago.com.ar/developers/es/docs/checkout-pro/additional-content/your-integrations/test/cards) (ej: Mastercard `5031 7557 3453 0604`, venc. `11/30`, CVV `123`, titular `APRO`).
3. Al volver del checkout, **el pedido se confirma solo** (vía el redirect del navegador).

### ngrok y webhook — opcionales
- El **webhook IPN** (notificación server-to-server) es lo único que necesita una URL pública (ngrok) y `MP_WEBHOOK_SECRET`. **No es necesario:** el pedido ya se confirma por el redirect. Sin ngrok, simplemente no se envía `notification_url`.
- Para mostrar el webhook procesando se puede usar *"Simular notificación"* desde el panel de MercadoPago.

### ⚠️ Divergencia documentada (vs. consigna §5.4)
La consigna pide `POST /pagos/crear` con token de tarjeta (CardPayment embebido). El equipo optó por **Checkout PRO (redirect)** porque el sandbox de CardPayment no era operativo. `POST /pagos/crear` queda como stub `501` con mensaje explicativo. La integración cubre lo central de la rúbrica: **webhook IPN con validación de firma HMAC + idempotency_key + entidad `Pago` persistida**.

---

## 📦 Stock del producto — derivado de insumos

El stock se gestiona **por insumo** (`Ingrediente.stock_cantidad`). El stock disponible de cada **producto** se **calcula** a partir de sus insumos:

```
stock_disponible = mín( ⌊ stock_insumo / cantidad_en_receta ⌋ )   sobre todos sus insumos
```

Se expone como campo de solo lectura `stock_disponible` en la respuesta de producto. Al crear un pedido se valida el stock de insumos; el inventario se descuenta al **confirmar** el pedido (y se restaura al cancelar uno confirmado).

> **Divergencia documentada (vs. consigna §3.2/§4.2):** la consigna define `Producto.stock_cantidad` editable por el rol STOCK. Como el catálogo se arma por receta, el stock del producto se deriva de sus insumos (no se edita a mano). La columna `producto.stock_cantidad` permanece en el modelo pero sin uso.

---

## Módulos y endpoints principales

Prefijo común: `/api/v1`

| Módulo | Endpoints | Acceso |
|---|---|---|
| **auth** | `/auth/register`, `/login`, `/refresh`, `/logout`, `/me`, `/google`, `/forgot-password`, `/reset-password` | público / autenticado |
| **categorias** | CRUD + árbol jerárquico (`/categorias/tree`) | lectura **pública**, escritura ADMIN |
| **ingredientes** | CRUD + export/import Excel | ADMIN / STOCK |
| **productos** | CRUD + `/disponibilidad` + `/destacar` + export/import Excel | lectura **pública**, escritura ADMIN/STOCK |
| **pedidos** | Crear, listar, `/avanzar`, `/cancelar`, `/historial`, callbacks de pago MP | CLIENT (propios) / ADMIN-PEDIDOS (todos) |
| **pagos** | Webhook IPN MercadoPago, redirect, consulta de pago | público (MP) / autenticado |
| **direcciones** | CRUD + `/principal` | usuario autenticado |
| **unidades** | Catálogo de unidades de medida | autenticado |
| **estadisticas** | `/ventas`, `/productos-top`, `/pedidos-por-estado`, `/ingresos`, `/resumen` | ADMIN |
| **uploads** | `POST /uploads/imagen`, `DELETE /uploads/imagen/{public_id}` (Cloudinary) | ADMIN / STOCK |
| **admin** | Gestión de usuarios y roles | ADMIN |
| **WebSocket** | `ws://localhost:8000/ws/pedidos` (cliente) · `/ws/admin/pedidos` (staff) — auth por `?token=<jwt>` | autenticado |

### Roles (RBAC)

| Rol | Capacidades |
|---|---|
| `ADMIN` | Acceso total: CRUD de catálogo, pedidos, usuarios, dashboard |
| `STOCK` | Insumos, productos y disponibilidad |
| `PEDIDOS` | Ver y avanzar estados de pedidos |
| `CLIENT` | Catálogo, carrito, pedidos y direcciones propias |

### Máquina de estados de pedidos (FSM v7)

```
PENDIENTE → CONFIRMADO → EN_PREP → ENTREGADO
    │            │           │
    └────────────┴───────────┴──────────→ CANCELADO
```

Cada transición queda registrada en `HistorialEstadoPedido` (append-only) y se emite por WebSocket a los clientes suscriptos.

---

## Seguridad

- **JWT**: access token (30 min) + refresh token con rotación (7 días).
- **Cookie HTTPOnly**: el access token también se setea como cookie; el backend acepta cookie o header `Authorization: Bearer`.
- **bcrypt**: hash de contraseñas con cost factor 12.
- **Rate limiting**: 5 intentos / 15 min por IP en `/auth/login` y `/auth/register`.
- **CORS**: configurado con `allow_credentials=True`.
- **Webhook MP**: validación de firma HMAC-SHA256.
- **Soft Delete**: ninguna entidad de negocio se elimina físicamente.

---

## Estructura del proyecto

```
Profe-Espejo/
├── main.py                  # Entry point FastAPI + lifespan (seed auto-run)
├── requirements.txt
├── .env.example             # Plantilla de variables de entorno
├── alembic/versions/        # Migraciones
└── app/
    ├── core/                # config, database, security, dependencies, links,
    │                        # base_repository, unit_of_work, websocket
    ├── db/
    │   └── seed.py          # Datos iniciales (roles, estados, usuarios, catálogo)
    └── modules/             # auth, categorias, ingredientes, productos, pedidos,
                             # pagos, direcciones, unidades, estadisticas, uploads, admin
```

---

## Tests

Suite con **pytest**: tests de servicio (UoW mockeado) + tests de integración con `TestClient` sobre una base PostgreSQL de test aislada (`foodstore_test_db`).

```bash
# Activar el venv primero
pytest                                  # toda la suite
pytest -v                               # detallado
pytest --cov=app --cov-report=term-missing   # con cobertura (≥ 60%)
```

---

## Comandos de referencia rápida

```bash
alembic upgrade head          # aplicar migraciones
python -m app.db.seed         # cargar datos iniciales
uvicorn main:app --reload     # iniciar servidor
alembic current               # ver migración actual
pytest                        # correr tests
```
