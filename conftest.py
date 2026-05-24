"""
conftest.py raiz - carga ANTES de la coleccion de tests.
Pre-importa todos los modelos ORM en el orden correcto para que SQLAlchemy
configure los mappers sin errores de nombres no resueltos.
"""
# Categoria e Ingrediente deben importarse ANTES que Producto
# porque Producto tiene Relationship("Categoria") y Relationship("Ingrediente")
import app.modules.categorias.model      # noqa: F401
import app.modules.ingredientes.model    # noqa: F401
import app.modules.productos.model       # noqa: F401
import app.modules.auth.model            # noqa: F401
import app.modules.usuarios.model        # noqa: F401
import app.modules.pagos.model           # noqa: F401
import app.modules.direcciones.model     # noqa: F401
import app.modules.pedidos.model         # noqa: F401
