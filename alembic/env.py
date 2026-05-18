from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel
from alembic import context

# ── Importar TODOS los modelos para que Alembic los detecte ───────────────────
from app.core.links import ProductoCategoria, ProductoIngrediente          # noqa
from app.modules.auth.model import Usuario, Rol, UsuarioRol, RefreshToken, PasswordResetToken  # noqa
from app.modules.categorias.model import Categoria                         # noqa
from app.modules.ingredientes.model import Ingrediente                     # noqa
from app.modules.productos.model import Producto                           # noqa
# Agregar aquí los modelos de pedidos, pagos, etc. cuando se implementen

from app.core.config import settings

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url, target_metadata=target_metadata, literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
