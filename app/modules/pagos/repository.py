from sqlmodel import Session


class PagoRepository:
    """Repository stub para pagos. Se implementa en el sprint correspondiente."""

    def __init__(self, session: Session):
        self.session = session
