from datetime import datetime
from typing import List, Optional, Tuple
from sqlmodel import Session, select

from app.core.base_repository import BaseRepository
from app.modules.direcciones.model import DireccionEntrega


class DireccionRepository(BaseRepository[DireccionEntrega]):
    """
    Repositorio de DireccionEntrega.
    Soft-delete aware: get_by_id filtra deleted_at IS NULL.
    Append-only methods? No — direcciones son editables.
    """

    def __init__(self, session: Session):
        super().__init__(session, DireccionEntrega)

    def get_by_id(self, direccion_id: int) -> Optional[DireccionEntrega]:
        return self.session.exec(
            select(DireccionEntrega).where(
                DireccionEntrega.id == direccion_id,
                DireccionEntrega.deleted_at == None,
            )
        ).first()

    def get_by_id_for_user(self, direccion_id: int, usuario_id: int) -> Optional[DireccionEntrega]:
        """Garantiza ownership: solo retorna si la dirección pertenece al usuario."""
        return self.session.exec(
            select(DireccionEntrega).where(
                DireccionEntrega.id == direccion_id,
                DireccionEntrega.usuario_id == usuario_id,
                DireccionEntrega.deleted_at == None,
            )
        ).first()

    def get_all_by_user(
        self,
        usuario_id: int,
        alias: Optional[str] = None,
        page: int = 1,
        size: int = 20,
    ) -> Tuple[List[DireccionEntrega], int]:
        query = select(DireccionEntrega).where(
            DireccionEntrega.usuario_id == usuario_id,
            DireccionEntrega.deleted_at == None,
        )
        if alias:
            query = query.where(DireccionEntrega.alias.icontains(alias))
        total = len(self.session.exec(query).all())
        offset = (page - 1) * size
        items = list(self.session.exec(query.offset(offset).limit(size)).all())
        return items, total

    def get_principal_for_user(self, usuario_id: int) -> Optional[DireccionEntrega]:
        return self.session.exec(
            select(DireccionEntrega).where(
                DireccionEntrega.usuario_id == usuario_id,
                DireccionEntrega.es_principal == True,
                DireccionEntrega.deleted_at == None,
            )
        ).first()

    def unset_all_principal_for_user(self, usuario_id: int) -> None:
        """
        Marca todas las direcciones del usuario como no-principales.
        Se llama antes de setear una nueva como principal para garantizar
        la invariante 'una sola principal por usuario'.
        Todo dentro de la misma transacción del UoW.
        """
        direcciones = self.session.exec(
            select(DireccionEntrega).where(
                DireccionEntrega.usuario_id == usuario_id,
                DireccionEntrega.es_principal == True,
                DireccionEntrega.deleted_at == None,
            )
        ).all()
        for d in direcciones:
            d.es_principal = False
            self.session.add(d)
        self.session.flush()

    def soft_delete(self, direccion: DireccionEntrega) -> None:
        direccion.deleted_at = datetime.utcnow()
        self.session.add(direccion)
        self.session.flush()