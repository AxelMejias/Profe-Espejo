"""
test_categorias_service.py - Tests para app/modules/categorias/service.py

Cubre: get_all, get_by_id, get_subcategorias, create, update, delete.
"""
import pytest
from fastapi import HTTPException
from unittest.mock import MagicMock, patch

from app.modules.categorias import service
from app.modules.categorias.schemas import CategoriaCreate, CategoriaUpdate
from tests.conftest import make_uow


def mock_categoria(id: int = 1, nombre: str = "Hamburguesas", parent_id=None):
    from datetime import datetime
    c = MagicMock()
    c.id = id
    c.nombre = nombre
    c.descripcion = "Desc"
    c.parent_id = parent_id
    c.created_at = datetime(2024, 1, 1)
    c.updated_at = None
    c.deleted_at = None
    return c


class TestGetAll:
    def test_retorna_lista_paginada(self):
        uow = make_uow()
        cats = [mock_categoria(1, "Burgers"), mock_categoria(2, "Bebidas")]
        uow.categorias.get_all.return_value = (cats, 2)

        result = service.get_all(uow)

        assert result.total == 2
        assert len(result.items) == 2

    def test_lista_vacia(self):
        uow = make_uow()
        uow.categorias.get_all.return_value = ([], 0)

        result = service.get_all(uow)

        assert result.total == 0
        assert result.pages == 0

    def test_pasa_filtro_nombre(self):
        uow = make_uow()
        uow.categorias.get_all.return_value = ([], 0)

        service.get_all(uow, nombre="Burger")

        uow.categorias.get_all.assert_called_with(nombre="Burger", page=1, size=20)


class TestGetById:
    def test_encontrado(self):
        uow = make_uow()
        uow.categorias.get_by_id.return_value = mock_categoria(3, "Postres")

        result = service.get_by_id(uow, 3)

        assert result.id == 3
        assert result.nombre == "Postres"

    def test_no_encontrado_lanza_404(self):
        uow = make_uow()
        uow.categorias.get_by_id.return_value = None

        with pytest.raises(HTTPException) as exc:
            service.get_by_id(uow, 999)

        assert exc.value.status_code == 404
        assert exc.value.detail["code"] == "CATEGORIA_NOT_FOUND"


class TestGetSubcategorias:
    def test_retorna_hijos(self):
        uow = make_uow()
        padre = mock_categoria(1)
        hijo1 = mock_categoria(2, "Sub1", parent_id=1)
        hijo2 = mock_categoria(3, "Sub2", parent_id=1)
        uow.categorias.get_by_id.return_value = padre
        uow.categorias.get_subcategorias.return_value = [hijo1, hijo2]

        result = service.get_subcategorias(uow, 1)

        assert len(result) == 2

    def test_padre_no_encontrado_lanza_404(self):
        uow = make_uow()
        uow.categorias.get_by_id.return_value = None

        with pytest.raises(HTTPException) as exc:
            service.get_subcategorias(uow, 99)

        assert exc.value.status_code == 404


class TestCreate:
    def test_crear_exitoso(self):
        uow = make_uow()
        uow.categorias.get_by_nombre.return_value = None
        nueva = mock_categoria(10, "Nueva")

        data = CategoriaCreate(nombre="Nueva")
        with patch("app.modules.categorias.service.Categoria", return_value=nueva):
            service.create(uow, data)

        uow.categorias.add.assert_called_once()

    def test_nombre_duplicado_lanza_409(self):
        uow = make_uow()
        uow.categorias.get_by_nombre.return_value = mock_categoria()

        with pytest.raises(HTTPException) as exc:
            service.create(uow, CategoriaCreate(nombre="Duplicada"))

        assert exc.value.status_code == 409
        assert exc.value.detail["code"] == "NOMBRE_CONFLICT"

    def test_parent_id_inexistente_lanza_404(self):
        uow = make_uow()
        uow.categorias.get_by_nombre.return_value = None
        uow.categorias.get_by_id.return_value = None

        with pytest.raises(HTTPException) as exc:
            service.create(uow, CategoriaCreate(nombre="Sub", parent_id=99))

        assert exc.value.status_code == 404
        assert exc.value.detail["code"] == "PARENT_NOT_FOUND"


class TestUpdate:
    def test_update_exitoso(self):
        uow = make_uow()
        cat = mock_categoria(1, "Viejo")
        uow.categorias.get_by_id.return_value = cat
        uow.categorias.add.return_value = cat

        result = service.update(uow, 1, CategoriaUpdate(nombre="Nuevo"))

        assert cat.nombre == "Nuevo"

    def test_update_no_encontrado_lanza_404(self):
        uow = make_uow()
        uow.categorias.get_by_id.return_value = None

        with pytest.raises(HTTPException) as exc:
            service.update(uow, 99, CategoriaUpdate(nombre="Inexistente"))

        assert exc.value.status_code == 404


class TestDelete:
    def test_delete_llama_soft_delete(self):
        uow = make_uow()
        cat = mock_categoria()
        uow.categorias.get_by_id.return_value = cat

        service.delete(uow, 1)

        uow.categorias.soft_delete.assert_called_once_with(cat)

    def test_delete_no_encontrado_lanza_404(self):
        uow = make_uow()
        uow.categorias.get_by_id.return_value = None

        with pytest.raises(HTTPException) as exc:
            service.delete(uow, 99)

        assert exc.value.status_code == 404
