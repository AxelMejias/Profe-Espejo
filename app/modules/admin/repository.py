from sqlmodel import Session


class AdminRepository:
    """Repository stub para admin. Se implementa en el sprint correspondiente."""

    def __init__(self, session: Session):
        self.session = session
