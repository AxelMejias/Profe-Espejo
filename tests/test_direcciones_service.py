"""
test_direcciones_service.py - Tests para app/modules/direcciones/service.py

Cubre: get_all, get_by_id, create, update, marcar_principal, delete.
"""
import pytest
from fastapi import HTTPException
from unittest.mock import MagicMock, patch

from app.modules.direcciones import service
from app.modules.direcciones.schemas import DireccionCreate, DireccionUpdate
from tests.conftest import make_uow

_PATCH_DIR = "app.modules.direcciones.service.DireccionEntrega"


def mock_direccion(
    id: int = 1,
    usuario_id: int = 1,
    linea1: str = "Av. Corrientes 1234",
    ciudad: str = "Buenos Aires",
    es_principal: bool = False,
):
    from datetime import datetime
    d = MagicMock()
    d.id = id
    d.usuario_id = usuario_id
    d.alias = None
    d.linea1 = linea1
    d.linea2 = None
    d.ciudad = ciudad
    d.provincia = None
    d.codigo_postal = None
    d.latitud = None
    d.longitud = None
    d.es_principal = es_principal
    d.created_at = datetime(2024, 1, 1)
    d.updated_at = None
    d.deleted_at = None
    return d


class TestGetAll:
    def test_retorna_paginado(self):
        uow = make_uow()
        uow.direcciones.get_all_by_user.return_value = ([mock_direccion(), mock_direccion(2)], 2)

        result = service.get_all(uow, usuario_id=1)

        assert result.total == 2
        assert len(result.items) == 2

    def test_filtra_por_usuario(self):
        uow = make_uow()
        uow.direcciones.get_all_by_user.return_value = ([], 0)

        service.get_all(uow, usuario_id=42)

        call_kwargs = uow.direcciones.get_all_by_user.call_args[1]
        assert call_kwargs.get("usuario_id") == 42


class TestGetById:
    def test_encontrado(self):
        uow = make_uow()
        uow.direcciones.get_by_id_for_user.return_value = mock_direccion(1, 1)

        result = service.get_by_id(uow, 1, usuario_id=1)

        assert result.id == 1

    def test_no_encontrado_lanza_404(self):
        uow = make_uow()
        uow.direcciones.get_by_id_for_user.return_value = None

        with pytest.raises(HTTPException) as exc:
            service.get_by_id(uow, 99, usuario_id=1)

        assert exc.value.status_code == 404
        assert exc.value.detail["code"] == "DIRECCION_NOT_FOUND"

    def test_no_puede_ver_direccion_de_otro_usuario(self):
        uow = make_uow()
        uow.direcciones.get_by_id_for_user.return_value = None

        with pytest.raises(HTTPException) as exc:
            service.get_by_id(uow, 1, usuario_id=999)

        assert exc.value.status_code == 404


class TestCreate:
    def test_crear_direccion_simple(self):
        uow = make_uow()
        nueva = mock_direccion(10, 1)

        data = DireccionCreate(linea1="Calle 123", ciudad="Rosario")
        with patch(_PATCH_DIR, return_value=nueva):
            service.create(uow, data, usuario_id=1)

        uow.direcciones.add.assert_called_once()

    def test_crear_como_principal_desmarca_otras(self):
        uow = make_uow()
        nueva = mock_direccion(10, 1, es_principal=True)

        data = DireccionCreate(linea1="Calle 123", ciudad="Rosario", es_principal=True)
        with patch(_PATCH_DIR, return_value=nueva):
            service.create(uow, data, usuario_id=1)

        uow.direcciones.unset_all_principal_for_user.assert_called_once_with(1)

    def test_crear_sin_principal_no_desmarca(self):
        uow = make_uow()
        nueva = mock_direccion()

        data = DireccionCreate(linea1="Calle 123", ciudad="Rosario", es_principal=False)
        with patch(_PATCH_DIR, return_value=nueva):
            service.create(uow, data, usuario_id=1)

        uow.direcciones.unset_all_principal_for_user.assert_not_called()


class TestUpdate:
    def test_update_exitoso(self):
        uow = make_uow()
        dir_ = mock_direccion()
        uow.direcciones.get_by_id_for_user.return_value = dir_
        uow.direcciones.add.return_value = dir_

        service.update(uow, 1, DireccionUpdate(ciudad="Cordoba"), usuario_id=1)

        assert dir_.ciudad == "Cordoba"

    def test_update_no_encontrado_lanza_404(self):
        uow = make_uow()
        uow.direcciones.get_by_id_for_user.return_value = None

        with pytest.raises(HTTPException) as exc:
            service.update(uow, 99, DireccionUpdate(ciudad="X"), usuario_id=1)

        assert exc.value.status_code == 404


class TestMarcarPrincipal:
    def test_marca_como_principal(self):
        uow = make_uow()
        dir_ = mock_direccion(es_principal=False)
        uow.direcciones.get_by_id_for_user.return_value = dir_
        uow.direcciones.add.return_value = dir_

        service.marcar_principal(uow, 1, usuario_id=1)

        uow.direcciones.unset_all_principal_for_user.assert_called_once_with(1)
        assert dir_.es_principal is True

    def test_desmarca_anteriores(self):
        uow = make_uow()
        dir_ = mock_direccion()
        uow.direcciones.get_by_id_for_user.return_value = dir_
        uow.direcciones.add.return_value = dir_

        service.marcar_principal(uow, 1, usuario_id=1)

        uow.direcciones.unset_all_principal_for_user.assert_called_once()

    def test_no_encontrada_lanza_404(self):
        uow = make_uow()
        uow.direcciones.get_by_id_for_user.return_value = None

        with pytest.raises(HTTPException) as exc:
            service.marcar_principal(uow, 99, usuario_id=1)

        assert exc.value.status_code == 404


class TestDelete:
    def test_delete_llama_soft_delete(self):
        uow = make_uow()
        dir_ = mock_direccion()
        uow.direcciones.get_by_id_for_user.return_value = dir_

        service.delete(uow, 1, usuario_id=1)

        uow.direcciones.soft_delete.assert_called_once_with(dir_)

    def test_delete_no_encontrado_lanza_404(self):
        uow = make_uow()
        uow.direcciones.get_by_id_for_user.return_value = None

        with pytest.raises(HTTPException) as exc:
            service.delete(uow, 99, usuario_id=1)

        assert exc.value.status_code == 404
