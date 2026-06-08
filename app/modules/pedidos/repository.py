from datetime import datetime
from typing import List, Optional, Tuple
from sqlmodel import Session, select

from app.core.base_repository import BaseRepository
from app.modules.pedidos.model import (
    Pedido, DetallePedido, EstadoPedido, FormaPago, HistorialEstadoPedido,
)


# ──────────────────────────────────────────────────────────────────────────────
# Catálogos
# ──────────────────────────────────────────────────────────────────────────────

class EstadoPedidoRepository(BaseRepository[EstadoPedido]):

    def __init__(self, session: Session):
        super().__init__(session, EstadoPedido)

    def get_by_codigo(self, codigo: str) -> Optional[EstadoPedido]:
        return self.session.exec(
            select(EstadoPedido).where(EstadoPedido.codigo == codigo)
        ).first()

    def get_all(self) -> List[EstadoPedido]:
        return list(
            self.session.exec(
                select(EstadoPedido).order_by(EstadoPedido.orden)
            ).all()
        )


class FormaPagoRepository(BaseRepository[FormaPago]):

    def __init__(self, session: Session):
        super().__init__(session, FormaPago)

    def get_by_codigo(self, codigo: str) -> Optional[FormaPago]:
        return self.session.exec(
            select(FormaPago).where(FormaPago.codigo == codigo)
        ).first()

    def get_all_habilitadas(self) -> List[FormaPago]:
        return list(
            self.session.exec(
                select(FormaPago).where(FormaPago.habilitado == True)
            ).all()
        )


# ──────────────────────────────────────────────────────────────────────────────
# Pedido (incluye operaciones sobre DetallePedido e HistorialEstadoPedido,
# que son parte del agregado "Pedido" en el modelo DDD).
#
# IMPORTANTE — Patrón append-only:
# HistorialEstadoPedido SOLO expone add_historial(). No hay update ni delete.
# La regla RN-03 se enforcea por ausencia del método.
# ──────────────────────────────────────────────────────────────────────────────

class PedidoRepository(BaseRepository[Pedido]):

    def __init__(self, session: Session):
        super().__init__(session, Pedido)

    # ── Queries sobre Pedido ─────────────────────────────────────────────────

    def get_by_id(self, pedido_id: int) -> Optional[Pedido]:
        return self.session.exec(
            select(Pedido).where(
                Pedido.id == pedido_id,
                Pedido.deleted_at == None,
            )
        ).first()

    def get_by_id_for_user(self, pedido_id: int, usuario_id: int) -> Optional[Pedido]:
        """Ownership-aware: garantiza que el CLIENT solo vea sus pedidos."""
        return self.session.exec(
            select(Pedido).where(
                Pedido.id == pedido_id,
                Pedido.usuario_id == usuario_id,
                Pedido.deleted_at == None,
            )
        ).first()

    def get_all(
        self,
        usuario_id: Optional[int] = None,
        estado_codigo: Optional[str] = None,
        excluir_estados: Optional[List[str]] = None,
        page: int = 1,
        size: int = 20,
    ) -> Tuple[List[Pedido], int]:
        """
        Si usuario_id está seteado ⇒ filtra a sus pedidos (CLIENT).
        Si es None ⇒ retorna todos (ADMIN / PEDIDOS).
        """
        query = select(Pedido).where(Pedido.deleted_at == None)
        if usuario_id is not None:
            query = query.where(Pedido.usuario_id == usuario_id)
        if estado_codigo:
            query = query.where(Pedido.estado_codigo == estado_codigo)
        if excluir_estados:
            query = query.where(Pedido.estado_codigo.not_in(excluir_estados))
        query = query.order_by(Pedido.created_at.desc())

        total = len(self.session.exec(query).all())
        offset = (page - 1) * size
        items = list(self.session.exec(query.offset(offset).limit(size)).all())
        return items, total

    def soft_delete(self, pedido: Pedido) -> None:
        pedido.deleted_at = datetime.utcnow()
        self.session.add(pedido)
        self.session.flush()

    # ── Detalle del pedido ───────────────────────────────────────────────────

    def get_detalles(self, pedido_id: int) -> List[DetallePedido]:
        return list(
            self.session.exec(
                select(DetallePedido).where(DetallePedido.pedido_id == pedido_id)
            ).all()
        )

    def add_detalle(self, detalle: DetallePedido) -> DetallePedido:
        self.session.add(detalle)
        self.session.flush()
        return detalle

    # ── Historial de estados (APPEND-ONLY: solo add_historial existe) ────────

    def get_historial(self, pedido_id: int) -> List[HistorialEstadoPedido]:
        """Reconstrucción cronológica del flujo de estados."""
        return list(
            self.session.exec(
                select(HistorialEstadoPedido)
                .where(HistorialEstadoPedido.pedido_id == pedido_id)
                .order_by(HistorialEstadoPedido.created_at.asc())
            ).all()
        )

    def add_historial(self, entry: HistorialEstadoPedido) -> HistorialEstadoPedido:
        """
        Append-only por diseño: este es el único método que toca historial_estado_pedido.
        No existen update_historial() ni delete_historial() — RN-03 enforced.
        """
        self.session.add(entry)
        self.session.flush()
        return entry

    def get_esperando_pago_expirados(self, cutoff: datetime) -> List[Pedido]:
        """Pedidos ESPERANDO_PAGO creados antes de `cutoff` (sin soft-delete)."""
        return list(self.session.exec(
            select(Pedido).where(
                Pedido.estado_codigo == "ESPERANDO_PAGO",
                Pedido.deleted_at == None,
                Pedido.created_at <= cutoff,
            )
        ).all())