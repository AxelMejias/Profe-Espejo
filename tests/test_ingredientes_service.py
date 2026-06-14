"""
test_ingredientes_service.py - Tests para app/modules/ingredientes/service.py

Cubre: get_all, get_by_id, create, update, delete.
"""
import pytest
from fastapi import HTTPException
from unittest.mock import MagicMock, patch

from app.modules.ingredientes import service
from app.modules.ingredientes.schemas import IngredienteCreate, IngredienteUpdate
from tests.conftest import make_uow


def mock_ingrediente(
    id: int = 1,
    nombre: str = "Tomate",
    es_alergeno: bool = False,
    deleted_at=None,
):
    from datetime import datetime
    from decimal import Decimal
    i = MagicMock()
    i.id = id
    i.nombre = nombre
    i.descripcion = "Descripcion"
    i.unidad_medida = "kg"
    i.es_alergeno = es_alergeno
    i.costo_unitario = Decimal("10.00")
    i.stock_cantidad = Decimal("100.000")
    i.stock_minimo = Decimal("10.000")
    i.es_producto_terminado = False
    i.created_at = datetime(2024, 1, 1)
    i.updated_at = None
    i.deleted_at = deleted_at
    return i


class TestGetAll:
    def test_retorna_lista_paginada(self):
        uow = make_uow()
        items = [mock_ingrediente(1), mock_ingrediente(2, "Queso")]
        uow.ingredientes.get_all.return_value = (items, 2)

        result = service.get_all(uow)

        assert result.total == 2
        assert len(result.items) == 2

    def test_filtro_por_nombre(self):
        uow = make_uow()
        uow.ingredientes.get_all.return_value = ([], 0)

        service.get_all(uow, nombre="Tom")

        call_kwargs = uow.ingredientes.get_all.call_args[1]
        assert call_kwargs.get("nombre") == "Tom"

    def test_filtro_por_es_alergeno(self):
        uow = make_uow()
        uow.ingredientes.get_all.return_value = ([], 0)

        service.get_all(uow, es_alergeno=True)

        call_kwargs = uow.ingredientes.get_all.call_args[1]
        assert call_kwargs.get("es_alergeno") is True

    def test_paginas_calculadas(self):
        uow = make_uow()
        uow.ingredientes.get_all.return_value = ([], 25)

        result = service.get_all(uow, page=1, size=10)

        assert result.pages == 3  # ceil(25/10)


class TestGetById:
    def test_encontrado(self):
        uow = make_uow()
        uow.ingredientes.get_by_id.return_value = mock_ingrediente(5, "Cebolla")

        result = service.get_by_id(uow, 5)

        assert result.id == 5
        assert result.nombre == "Cebolla"

    def test_no_encontrado_lanza_404(self):
        uow = make_uow()
        uow.ingredientes.get_by_id.return_value = None

        with pytest.raises(HTTPException) as exc:
            service.get_by_id(uow, 999)

        assert exc.value.status_code == 404
        assert exc.value.detail["code"] == "INGREDIENTE_NOT_FOUND"


class TestCreate:
    def test_crear_exitoso(self):
        uow = make_uow()
        uow.ingredientes.get_by_nombre.return_value = None
        nuevo = mock_ingrediente(10, "Lechuga")

        data = IngredienteCreate(
            nombre="Lechuga", unidad_medida="kg", es_alergeno=False
        )
        with patch("app.modules.ingredientes.service.Ingrediente", return_value=nuevo):
            service.create(uow, data)

        uow.ingredientes.add.assert_called_once()

    def test_nombre_duplicado_lanza_409(self):
        uow = make_uow()
        uow.ingredientes.get_by_nombre.return_value = mock_ingrediente()

        with pytest.raises(HTTPException) as exc:
            service.create(uow, IngredienteCreate(nombre="Tomate", unidad_medida="kg", es_alergeno=False))

        assert exc.value.status_code == 409
        assert exc.value.detail["code"] == "NOMBRE_CONFLICT"

    def test_alergeno_se_guarda(self):
        uow = make_uow()
        uow.ingredientes.get_by_nombre.return_value = None
        ingrediente_creado = mock_ingrediente(1, "Mani", es_alergeno=True)

        data = IngredienteCreate(nombre="Mani", unidad_medida="gr", es_alergeno=True)
        with patch("app.modules.ingredientes.service.Ingrediente", return_value=ingrediente_creado):
            result = service.create(uow, data)

        assert result.es_alergeno is True


class TestUpdate:
    def test_update_nombre_exitoso(self):
        uow = make_uow()
        ing = mock_ingrediente(1, "Viejo")
        uow.ingredientes.get_by_id.return_value = ing
        uow.ingredientes.get_by_nombre.return_value = None
        uow.ingredientes.add.return_value = ing

        service.update(uow, 1, IngredienteUpdate(nombre="Nuevo"))

        assert ing.nombre == "Nuevo"

    def test_update_nombre_duplicado_lanza_409(self):
        uow = make_uow()
        ing = mock_ingrediente(1, "Original")
        uow.ingredientes.get_by_id.return_value = ing
        uow.ingredientes.get_by_nombre.return_value = mock_ingrediente(2, "Ocupado")

        with pytest.raises(HTTPException) as exc:
            service.update(uow, 1, IngredienteUpdate(nombre="Ocupado"))

        assert exc.value.status_code == 409
        assert exc.value.detail["code"] == "NOMBRE_CONFLICT"

    def test_update_mismo_nombre_no_conflicto(self):
        """Cambiar otros campos sin tocar el nombre no debe dar conflicto."""
        uow = make_uow()
        ing = mock_ingrediente(1, "Tomate")
        uow.ingredientes.get_by_id.return_value = ing
        uow.ingredientes.add.return_value = ing

        service.update(uow, 1, IngredienteUpdate(es_alergeno=True))

        uow.ingredientes.get_by_nombre.assert_not_called()

    def test_update_no_encontrado_lanza_404(self):
        uow = make_uow()
        uow.ingredientes.get_by_id.return_value = None

        with pytest.raises(HTTPException) as exc:
            service.update(uow, 99, IngredienteUpdate(nombre="Inexistente"))

        assert exc.value.status_code == 404


class TestDelete:
    def test_delete_llama_soft_delete(self):
        uow = make_uow()
        ing = mock_ingrediente()
        uow.ingredientes.get_by_id.return_value = ing

        service.delete(uow, 1)

        uow.ingredientes.soft_delete.assert_called_once_with(ing)

    def test_delete_no_encontrado_lanza_404(self):
        uow = make_uow()
        uow.ingredientes.get_by_id.return_value = None

        with pytest.raises(HTTPException) as exc:
            service.delete(uow, 99)

        assert exc.value.status_code == 404
        assert exc.value.detail["code"] == "INGREDIENTE_NOT_FOUND"
