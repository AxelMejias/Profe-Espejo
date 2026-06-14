"""
test_admin_service.py — Tests para app/modules/admin/service.py

Cubre: get_all, get_by_id, update, delete, asignar_rol, remover_rol.
"""
import pytest
from fastapi import HTTPException
from unittest.mock import MagicMock, patch

from app.modules.admin import service
from app.modules.admin.schemas import UsuarioAdminUpdate, AsignarRolRequest
from tests.conftest import make_uow, mock_usuario, mock_rol


def _setup_uow_con_usuario(usuario=None):
    uow = make_uow()
    uow.usuarios_admin.get_by_id.return_value = usuario
    uow.usuarios_admin.get_roles.return_value = []
    return uow


class TestGetAll:
    def test_get_all_retorna_paginado(self):
        uow = make_uow()
        u1 = mock_usuario(id=1, email="a@test.com")
        u2 = mock_usuario(id=2, email="b@test.com")
        uow.usuarios_admin.get_all.return_value = ([u1, u2], 2)
        uow.usuarios_admin.get_roles.return_value = []

        result = service.get_all(uow, page=1, size=20)

        assert result.total == 2
        assert result.page == 1
        assert len(result.items) == 2

    def test_get_all_paginas_calculadas(self):
        uow = make_uow()
        uow.usuarios_admin.get_all.return_value = ([], 45)
        uow.usuarios_admin.get_roles.return_value = []

        result = service.get_all(uow, page=1, size=20)

        assert result.pages == 3  # ceil(45/20)

    def test_get_all_sin_resultados(self):
        uow = make_uow()
        uow.usuarios_admin.get_all.return_value = ([], 0)

        result = service.get_all(uow, page=1, size=20)

        assert result.total == 0
        assert result.pages == 0


class TestGetById:
    def test_get_by_id_encontrado(self):
        uow = _setup_uow_con_usuario(mock_usuario(id=5, email="x@test.com"))
        uow.usuarios_admin.get_roles.return_value = [mock_rol("STOCK")]

        result = service.get_by_id(uow, 5)

        assert result.id == 5
        assert result.roles[0].codigo == "STOCK"

    def test_get_by_id_no_encontrado_lanza_404(self):
        uow = _setup_uow_con_usuario(None)

        with pytest.raises(HTTPException) as exc:
            service.get_by_id(uow, 999)

        assert exc.value.status_code == 404
        assert exc.value.detail["code"] == "USER_NOT_FOUND"


class TestUpdate:
    def test_update_campos_parciales(self):
        uow = make_uow()
        usuario = mock_usuario(id=1)
        uow.usuarios_admin.get_by_id.return_value = usuario
        uow.usuarios_admin.get_roles.return_value = []

        data = UsuarioAdminUpdate(nombre="NuevoNombre")
        service.update(uow, 1, data)

        assert usuario.nombre == "NuevoNombre"

    def test_update_usuario_no_existe_lanza_404(self):
        uow = _setup_uow_con_usuario(None)

        with pytest.raises(HTTPException) as exc:
            service.update(uow, 99, UsuarioAdminUpdate(nombre="X"))

        assert exc.value.status_code == 404

    def test_update_actualiza_updated_at(self):
        uow = make_uow()
        usuario = mock_usuario()
        uow.usuarios_admin.get_by_id.return_value = usuario
        uow.usuarios_admin.get_roles.return_value = []

        service.update(uow, 1, UsuarioAdminUpdate(celular="1234567890"))

        assert usuario.updated_at is not None


class TestDelete:
    def test_delete_llama_soft_delete(self):
        uow = make_uow()
        usuario = mock_usuario()
        uow.usuarios_admin.get_by_id.return_value = usuario

        service.delete(uow, 1)

        uow.usuarios_admin.soft_delete.assert_called_once_with(usuario)

    def test_delete_usuario_no_existe_lanza_404(self):
        uow = _setup_uow_con_usuario(None)

        with pytest.raises(HTTPException) as exc:
            service.delete(uow, 99)

        assert exc.value.status_code == 404


class TestAsignarRol:
    def test_asignar_rol_exitoso(self):
        uow = make_uow()
        usuario = mock_usuario(id=1)
        uow.usuarios_admin.get_by_id.return_value = usuario
        uow.usuarios_admin.get_roles.return_value = [mock_rol("STOCK")]
        uow.usuarios_admin.has_rol.return_value = False

        # Mock select(Rol) vía uow.session.exec
        rol = mock_rol("STOCK")
        uow.session.exec.return_value.first.return_value = rol

        result = service.asignar_rol(uow, 1, "STOCK", actor_id=99)

        uow.usuarios_admin.add_rol.assert_called_once()
        assert result.roles[0].codigo == "STOCK"

    def test_asignar_rol_no_existe_lanza_404(self):
        uow = make_uow()
        uow.usuarios_admin.get_by_id.return_value = mock_usuario()
        uow.usuarios_admin.get_rol.return_value = None  # rol no existe

        with pytest.raises(HTTPException) as exc:
            service.asignar_rol(uow, 1, "ROL_FAKE", actor_id=1)

        assert exc.value.status_code == 404
        assert exc.value.detail["code"] == "ROL_NOT_FOUND"

    def test_asignar_rol_duplicado_lanza_409(self):
        uow = make_uow()
        uow.usuarios_admin.get_by_id.return_value = mock_usuario()
        uow.usuarios_admin.has_rol.return_value = True  # ya tiene el rol
        uow.session.exec.return_value.first.return_value = mock_rol("ADMIN")

        with pytest.raises(HTTPException) as exc:
            service.asignar_rol(uow, 1, "ADMIN", actor_id=1)

        assert exc.value.status_code == 409
        assert exc.value.detail["code"] == "ROL_ALREADY_ASSIGNED"


class TestRemoverRol:
    def test_remover_rol_exitoso(self):
        uow = make_uow()
        uow.usuarios_admin.get_by_id.return_value = mock_usuario()
        uow.usuarios_admin.remove_rol.return_value = True
        uow.usuarios_admin.get_roles.return_value = []

        result = service.remover_rol(uow, 1, "CLIENT")

        uow.usuarios_admin.remove_rol.assert_called_once_with(1, "CLIENT")

    def test_remover_rol_no_asignado_lanza_404(self):
        uow = make_uow()
        uow.usuarios_admin.get_by_id.return_value = mock_usuario()
        uow.usuarios_admin.remove_rol.return_value = False  # no tenía ese rol

        with pytest.raises(HTTPException) as exc:
            service.remover_rol(uow, 1, "STOCK")

        assert exc.value.status_code == 404
        assert exc.value.detail["code"] == "ROL_NOT_ASSIGNED"
