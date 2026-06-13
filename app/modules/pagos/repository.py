from typing import Optional
from sqlmodel import Session, select

from app.core.base_repository import BaseRepository
from app.modules.pagos.model import Pago


class PagoRepository(BaseRepository[Pago]):
    """Repositorio del agregado Pago. Recibe la sesión del UoW (no abre la suya)."""

    def __init__(self, session: Session):
        super().__init__(session, Pago)

    def get_by_external_reference(self, external_reference: str) -> Optional[Pago]:
        return self.session.exec(
            select(Pago).where(Pago.external_reference == external_reference)
        ).first()

    def get_by_mp_payment_id(self, mp_payment_id: int) -> Optional[Pago]:
        return self.session.exec(
            select(Pago).where(Pago.mp_payment_id == mp_payment_id)
        ).first()
