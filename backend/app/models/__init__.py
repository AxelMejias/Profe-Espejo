# Importar en orden correcto para evitar problemas de referencias circulares:
# 1. Tablas de enlace (sin Relationship)
# 2. Modelos principales
from app.models.links import ProductoCategoria, ProductoIngrediente
from app.models.categoria import Categoria
from app.models.ingrediente import Ingrediente
from app.models.producto import Producto

__all__ = [
    "ProductoCategoria",
    "ProductoIngrediente",
    "Categoria",
    "Ingrediente",
    "Producto",
]
