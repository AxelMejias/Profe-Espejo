"""
test_unidades_service.py — Tests para app/modules/unidades/service.py

Catálogo UnidadMedida (ERD v7). Cubre:
  - create: éxito, nombre duplicado (409), símbolo duplicado (409)
  - get_by_id: not found (404)
  - get_all: lista
  - update: not found (404), éxito
  - delete: not found (404), éxito (hard delete)
"""
from unittest.mock import MagicMock
import pytest
from fastapi import HTTPException

from app.modules.unidades import service
from app.modules.unidades.schemas import UnidadMedidaCreate, UnidadMedidaUpdate
from tests.conftest import make_uow


def _assign_id(u):
    u.id = 1
    return u


def _mock_unidad(id=1, nombre="kilogramo", simbolo="kg", tipo="peso"):
    u = MagicMock()
    u.id = id
    u.nombre = nombre
    u.simbolo = simbolo
    u.tipo = tipo
    u.created_at = "2026-01-01T00:00:00"
    return u


class TestCreate:

    def test_create_exitoso(self):
        uow = make_uow()
        uow.unidades.get_by_nombre.return_value = None
        uow.unidades.get_by_simbolo.return_value = None
        uow.unidades.add.side_effect = _assign_id

        data = UnidadMedidaCreate(nombre="kilogramo", simbolo="kg", tipo="peso")
        result = service.create(uow, data)

        assert result.nombre == "kilogramo"
        assert result.simbolo == "kg"
        uow.unidades.add.assert_called_once()

    def test_create_nombre_duplicado_409(self):
        uow = make_uow()
        uow.unidades.get_by_nombre.return_value = _mock_unidad()

        with pytest.raises(HTTPException) as exc:
            service.create(uow, UnidadMedidaCreate(nombre="kilogramo", simbolo="kg", tipo="peso"))
        assert exc.value.status_code == 409
        assert exc.value.detail["code"] == "NOMBRE_CONFLICT"

    def test_create_simbolo_duplicado_409(self):
        uow = make_uow()
        uow.unidades.get_by_nombre.return_value = None
        uow.unidades.get_by_simbolo.return_value = _mock_unidad()

        with pytest.raises(HTTPException) as exc:
            service.create(uow, UnidadMedidaCreate(nombre="otra", simbolo="kg", tipo="peso"))
        assert exc.value.status_code == 409
        assert exc.value.detail["code"] == "SIMBOLO_CONFLICT"


class TestGetById:

    def test_not_found_404(self):
        uow = make_uow()
        uow.unidades.get_by_id.return_value = None
        with pytest.raises(HTTPException) as exc:
            service.get_by_id(uow, 99)
        assert exc.value.status_code == 404


class TestGetAll:

    def test_retorna_lista(self):
        uow = make_uow()
        uow.unidades.get_all.return_value = [_mock_unidad(), _mock_unidad(2, "gramo", "g", "peso")]
        result = service.get_all(uow)
        assert len(result) == 2
        assert result[1].simbolo == "g"


class TestUpdate:

    def test_not_found_404(self):
        uow = make_uow()
        uow.unidades.get_by_id.return_value = None
        with pytest.raises(HTTPException) as exc:
            service.update(uow, 99, UnidadMedidaUpdate(nombre="x"))
        assert exc.value.status_code == 404

    def test_update_exitoso(self):
        uow = make_uow()
        unidad = _mock_unidad()
        uow.unidades.get_by_id.return_value = unidad
        uow.unidades.get_by_nombre.return_value = None
        uow.unidades.get_by_simbolo.return_value = None

        result = service.update(uow, 1, UnidadMedidaUpdate(tipo="masa"))
        assert unidad.tipo == "masa"
        uow.unidades.add.assert_called_once()


class TestDelete:

    def test_not_found_404(self):
        uow = make_uow()
        uow.unidades.get_by_id.return_value = None
        with pytest.raises(HTTPException) as exc:
            service.delete(uow, 99)
        assert exc.value.status_code == 404

    def test_delete_exitoso(self):
        uow = make_uow()
        unidad = _mock_unidad()
        uow.unidades.get_by_id.return_value = unidad
        service.delete(uow, 1)
        uow.unidades.hard_delete.assert_called_once_with(unidad)
