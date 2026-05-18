from sqlmodel import Session, select
from app.core.database import engine
from app.modules.auth.model import Rol, Usuario, UsuarioRol
from app.core.security import hash_password


def seed():
    with Session(engine) as session:
        _seed_roles(session)
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
