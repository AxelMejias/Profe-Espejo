from sqlmodel import Session


class DireccionRepository:
    """Repository stub para direcciones. Se implementa en el sprint correspondiente."""

    def __init__(self, session: Session):
        self.session = session
