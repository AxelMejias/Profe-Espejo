from sqlmodel import Session, select
from app.core.database import engine
from app.core.security import hash_password

from app.modules.auth.model import Rol, Usuario, UsuarioRol
from app.modules.pedidos.model import EstadoPedido, FormaPago
from app.modules.direcciones.model import DireccionEntrega  # noqa: F401 — registra el mapper


def seed():
    with Session(engine) as session:
        _seed_roles(session)
        _seed_estados_pedido(session)
        _seed_formas_pago(session)
        _seed_admin(session)
        print("Seed completado.")


def _seed_roles(session: Session):
    roles = [
        Rol(codigo="ADMIN",   nombre="Administrador",      descripcion="Acceso total al sistema"),
        Rol(codigo="STOCK",   nombre="Gestor de Stock",    descripcion="Gestión de inventario"),
        Rol(codigo="PEDIDOS", nombre="Gestor de Pedidos",  descripcion="Gestión de pedidos"),
        Rol(codigo="CLIENT",  nombre="Cliente",            descripcion="Cliente de la tienda"),
    ]
    for rol in roles:
        if not session.exec(select(Rol).where(Rol.codigo == rol.codigo)).first():
            session.add(rol)
    session.commit()


def _seed_estados_pedido(session: Session):
    estados = [
        EstadoPedido(codigo="PENDIENTE",  descripcion="Pendiente de confirmación", orden=1, es_terminal=False),
        EstadoPedido(codigo="CONFIRMADO", descripcion="Confirmado",                orden=2, es_terminal=False),
        EstadoPedido(codigo="EN_PREP",    descripcion="En preparación",            orden=3, es_terminal=False),
        EstadoPedido(codigo="EN_CAMINO",  descripcion="En camino",                 orden=4, es_terminal=False),
        EstadoPedido(codigo="ENTREGADO",  descripcion="Entregado",                 orden=5, es_terminal=True),
        EstadoPedido(codigo="CANCELADO",  descripcion="Cancelado",                 orden=6, es_terminal=True),
    ]
    for estado in estados:
        if not session.exec(select(EstadoPedido).where(EstadoPedido.codigo == estado.codigo)).first():
            session.add(estado)
    session.commit()


def _seed_formas_pago(session: Session):
    # Nota: la lógica funcional de MercadoPago está fuera de alcance (Parcial 2).
    # La tabla existe a nivel estructura para respetar el diagrama UML.
    formas = [
        FormaPago(codigo="EFECTIVO",     descripcion="Efectivo (retiro en local)", habilitado=True),
        FormaPago(codigo="TRANSFERENCIA", descripcion="Transferencia bancaria",     habilitado=True),
        FormaPago(codigo="MERCADOPAGO",  descripcion="MercadoPago",                habilitado=False),
    ]
    for forma in formas:
        if not session.exec(select(FormaPago).where(FormaPago.codigo == forma.codigo)).first():
            session.add(forma)
    session.commit()


def _seed_admin(session: Session):
    if session.exec(select(Usuario).where(Usuario.email == "admin@foodstore.com")).first():
        return
    admin = Usuario(
        nombre="Admin",
        apellido="FoodStore",
        email="admin@foodstore.com",
        password_hash=hash_password("Admin1234!"),
    )
    session.add(admin)
    session.flush()
    session.add(UsuarioRol(usuario_id=admin.id, rol_codigo="ADMIN"))
    session.commit()


if __name__ == "__main__":
    seed()