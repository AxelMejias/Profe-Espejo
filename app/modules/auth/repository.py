import hashlib
from datetime import datetime
from typing import Optional
from sqlmodel import Session, select
from app.modules.auth.model import Usuario, UsuarioRol, Rol, RefreshToken, PasswordResetToken


class UsuarioRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_email(self, email: str) -> Optional[Usuario]:
        return self.session.exec(
            select(Usuario).where(Usuario.email == email, Usuario.deleted_at == None)
        ).first()

    def get_by_id(self, usuario_id: int) -> Optional[Usuario]:
        return self.session.exec(
            select(Usuario).where(Usuario.id == usuario_id, Usuario.deleted_at == None)
        ).first()

    def add(self, usuario: Usuario) -> Usuario:
        self.session.add(usuario)
        self.session.flush()
        self.session.refresh(usuario)
        return usuario

    def get_roles(self, usuario_id: int) -> list[Rol]:
        return list(
            self.session.exec(
                select(Rol).join(UsuarioRol, Rol.codigo == UsuarioRol.rol_codigo).where(
                    UsuarioRol.usuario_id == usuario_id
                )
            ).all()
        )

    def add_rol(self, usuario_rol: UsuarioRol) -> None:
        self.session.add(usuario_rol)
        self.session.flush()


class RefreshTokenRepository:
    def __init__(self, session: Session):
        self.session = session

    @staticmethod
    def _hash(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def add(self, token: RefreshToken) -> RefreshToken:
        self.session.add(token)
        self.session.flush()
        return token

    def get_active_by_token(self, raw_token: str) -> Optional[RefreshToken]:
        token_hash = self._hash(raw_token)
        return self.session.exec(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.revoked_at == None,
            )
        ).first()

    def revoke(self, token: RefreshToken) -> None:
        token.revoked_at = datetime.utcnow()
        self.session.add(token)
        self.session.flush()

    def revoke_all_for_user(self, usuario_id: int) -> None:
        tokens = self.session.exec(
            select(RefreshToken).where(
                RefreshToken.usuario_id == usuario_id,
                RefreshToken.revoked_at == None,
            )
        ).all()
        now = datetime.utcnow()
        for t in tokens:
            t.revoked_at = now
            self.session.add(t)
        self.session.flush()


class PasswordResetTokenRepository:
    def __init__(self, session: Session):
        self.session = session

    @staticmethod
    def _hash(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def add(self, token: PasswordResetToken) -> PasswordResetToken:
        self.session.add(token)
        self.session.flush()
        return token

    def get_valid_by_token(self, raw_token: str) -> Optional[PasswordResetToken]:
        token_hash = self._hash(raw_token)
        return self.session.exec(
            select(PasswordResetToken).where(
                PasswordResetToken.token_hash == token_hash,
                PasswordResetToken.used_at == None,
                PasswordResetToken.expires_at > datetime.utcnow(),
            )
        ).first()

    def mark_used(self, token: PasswordResetToken) -> None:
        token.used_at = datetime.utcnow()
        self.session.add(token)
        self.session.flush()
