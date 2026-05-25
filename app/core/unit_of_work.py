from sqlmodel import Session
from app.core.database import engine


class UnitOfWork:
    """
    Patrón Unit of Work.
    Abre la sesión al entrar, hace commit al salir sin excepción,
    rollback automático si ocurre un error.

    Uso correcto (en el router):
        with UnitOfWork() as uow:
            resultado = service.hacer_algo(uow, datos)

    Regla: el Service NUNCA crea su propio UoW.
    Recibe uow como parámetro y opera sobre uow.<repo>.
    """

    def __init__(self):
        self.session: Session = Session(engine)

    def __enter__(self) -> "UnitOfWork":
        # Módulos existentes
        from app.modules.auth.repository import (
            UsuarioRepository,
            RefreshTokenRepository,
            PasswordResetTokenRepository,
        )
        from app.modules.categorias.repository import CategoriaRepository
        from app.modules.ingredientes.repository import IngredienteRepository
        from app.modules.productos.repository import ProductoRepository

        # Módulos implementados en Parcial 2
        from app.modules.pedidos.repository import (
            PedidoRepository,
            EstadoPedidoRepository,
            FormaPagoRepository,
        )
        from app.modules.direcciones.repository import DireccionRepository

        # Stubs (excluidos por restricción del Parcial 2)
        from app.modules.pagos.repository import PagoRepository
        from app.modules.admin.repository import UsuarioAdminRepository

        self.usuarios = UsuarioRepository(self.session)
        self.refresh_tokens = RefreshTokenRepository(self.session)
        self.reset_tokens = PasswordResetTokenRepository(self.session)

        self.categorias = CategoriaRepository(self.session)
        self.ingredientes = IngredienteRepository(self.session)
        self.productos = ProductoRepository(self.session)

        self.pedidos = PedidoRepository(self.session)
        self.estados_pedido = EstadoPedidoRepository(self.session)
        self.formas_pago = FormaPagoRepository(self.session)
        self.direcciones = DireccionRepository(self.session)

        self.pagos = PagoRepository(self.session)
        self.usuarios_admin = UsuarioAdminRepository(self.session)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.session.rollback()
        else:
            self.session.commit()
        self.session.close()

    def flush(self):
        """Sincroniza con la BD sin hacer commit (para obtener IDs generados)."""
        self.session.flush()