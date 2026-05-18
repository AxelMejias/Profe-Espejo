from sqlmodel import Session


class PedidoRepository:
    """Repository stub para pedidos. Se implementa en el sprint correspondiente."""

    def __init__(self, session: Session):
        self.session = session
