from typing import List, Optional
from sqlmodel import Session, select

from app.core.base_repository import BaseRepository
from app.modules.unidades.model import UnidadMedida


class UnidadMedidaRepository(BaseRepository[UnidadMedida]):
    """Repositorio del catálogo UnidadMedida. Recibe la sesión del UoW."""

    def __init__(self, session: Session):
        super().__init__(session, UnidadMedida)

    def get_by_nombre(self, nombre: str) -> Optional[UnidadMedida]:
        return self.session.exec(
            select(UnidadMedida).where(UnidadMedida.nombre == nombre)
        ).first()

    def get_by_simbolo(self, simbolo: str) -> Optional[UnidadMedida]:
        return self.session.exec(
            select(UnidadMedida).where(UnidadMedida.simbolo == simbolo)
        ).first()

    def get_all(self) -> List[UnidadMedida]:
        return list(
            self.session.exec(
                select(UnidadMedida).order_by(UnidadMedida.tipo, UnidadMedida.nombre)
            ).all()
        )
