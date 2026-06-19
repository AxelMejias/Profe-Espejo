import math
from datetime import datetime
from typing import List, Optional, Tuple
from sqlmodel import Session, select

from app.modules.auth.model import Usuario, UsuarioRol, Rol


class UsuarioAdminRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_all(
        self,
        rol_codigo: Optional[str] = None,
        page: int = 1,
        size: int = 20,
    ) -> Tuple[List[Usuario], int]:
        query = select(Usuario).where(Usuario.deleted_at == None)

        if rol_codigo:
            query = (
                query
                .join(UsuarioRol, UsuarioRol.usuario_id == Usuario.id)
                .where(UsuarioRol.rol_codigo == rol_codigo)
            )

        total = len(self.session.exec(query).all())
        offset = (page - 1) * size
        items = list(self.session.exec(query.offset(offset).limit(size)).all())
        return items, total

    def get_by_id(self, usuario_id: int) -> Optional[Usuario]:
        return self.session.exec(
            select(Usuario).where(
                Usuario.id == usuario_id,
                Usuario.deleted_at == None,
            )
        ).first()

    def get_roles(self, usuario_id: int) -> List[Rol]:
        return list(
            self.session.exec(
                select(Rol)
                .join(UsuarioRol, Rol.codigo == UsuarioRol.rol_codigo)
                .where(UsuarioRol.usuario_id == usuario_id)
            ).all()
        )

    def has_rol(self, usuario_id: int, rol_codigo: str) -> bool:
        return bool(
            self.session.exec(
                select(UsuarioRol).where(
                    UsuarioRol.usuario_id == usuario_id,
                    UsuarioRol.rol_codigo == rol_codigo,
                )
            ).first()
        )

    def count_active_admins(self) -> int:
        """Cantidad de usuarios ACTIVOS (no soft-deleted) con rol ADMIN."""
        return len(
            self.session.exec(
                select(UsuarioRol)
                .join(Usuario, Usuario.id == UsuarioRol.usuario_id)
                .where(
                    UsuarioRol.rol_codigo == "ADMIN",
                    Usuario.deleted_at == None,  # noqa: E711
                )
            ).all()
        )

    def add_rol(self, usuario_rol: UsuarioRol) -> None:
        self.session.add(usuario_rol)
        self.session.flush()

    def remove_rol(self, usuario_id: int, rol_codigo: str) -> bool:
        ur = self.session.exec(
            select(UsuarioRol).where(
                UsuarioRol.usuario_id == usuario_id,
                UsuarioRol.rol_codigo == rol_codigo,
            )
        ).first()
        if not ur:
            return False
        self.session.delete(ur)
        self.session.flush()
        return True

    def add(self, entity) -> None:
        self.session.add(entity)
        self.session.flush()

    def get_rol(self, rol_codigo: str) -> Optional[Rol]:
        return self.session.exec(
            select(Rol).where(Rol.codigo == rol_codigo)
        ).first()

    def soft_delete(self, usuario: Usuario) -> None:
        usuario.deleted_at = datetime.utcnow()
        self.session.add(usuario)
        self.session.flush()