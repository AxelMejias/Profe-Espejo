from sqlmodel import Session


class UsuarioAdminRepository:
    """Repository stub para usuarios. Se implementa en el sprint correspondiente."""

    def __init__(self, session: Session):
        self.session = session
