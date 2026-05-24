"""
test_auth_service.py — Tests para app/modules/auth/service.py

Cubre: register, login, refresh, logout, get_me, forgot_password, reset_password.
Usa mock de UoW para evitar DB real.
"""
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

from app.modules.auth.service import auth_service
from app.modules.auth.schemas import (
    LoginRequest,
    RegisterRequest,
    RefreshRequest,
)
from tests.conftest import make_uow, mock_usuario, mock_rol


# ──────────────────────────────────────────────────────────────────────────────
# register
# ──────────────────────────────────────────────────────────────────────────────

class TestRegister:
    def test_registro_exitoso(self):
        uow = make_uow()
        uow.usuarios.get_by_email.return_value = None  # email libre
        usuario = mock_usuario()
        uow.usuarios.add.return_value = usuario
        uow.usuarios.get_roles.return_value = [mock_rol("CLIENT")]

        data = RegisterRequest(
            nombre="Juan", apellido="Perez",
            email="juan@test.com", password="Pass123!",
        )
        result = auth_service.register(uow, data)

        assert result.email == "juan@test.com"
        assert result.nombre == "Juan"
        uow.usuarios.add.assert_called_once()
        uow.usuarios.add_rol.assert_called_once()

    def test_email_ya_registrado_lanza_409(self):
        uow = make_uow()
        uow.usuarios.get_by_email.return_value = mock_usuario()  # ya existe

        data = RegisterRequest(
            nombre="Juan", apellido="Perez",
            email="duplicado@test.com", password="Pass123!",
        )
        with pytest.raises(HTTPException) as exc:
            auth_service.register(uow, data)

        assert exc.value.status_code == 409
        assert exc.value.detail["code"] == "EMAIL_CONFLICT"

    def test_registro_asigna_rol_client(self):
        uow = make_uow()
        uow.usuarios.get_by_email.return_value = None
        usuario = mock_usuario(id=5)
        uow.usuarios.add.return_value = usuario
        uow.usuarios.get_roles.return_value = [mock_rol("CLIENT")]

        data = RegisterRequest(
            nombre="Ana", apellido="Lopez",
            email="ana@test.com", password="Pass123!",
        )
        auth_service.register(uow, data)

        # Verificar que se asignó el rol CLIENT
        call_args = uow.usuarios.add_rol.call_args[0][0]
        assert call_args.rol_codigo == "CLIENT"


# ──────────────────────────────────────────────────────────────────────────────
# login
# ──────────────────────────────────────────────────────────────────────────────

class TestLogin:
    def test_login_exitoso(self):
        uow = make_uow()
        usuario = mock_usuario()
        uow.usuarios.get_by_email.return_value = usuario
        uow.usuarios.get_roles.return_value = [mock_rol("CLIENT")]
        uow.refresh_tokens.add.return_value = MagicMock()

        with patch("app.modules.auth.service.verify_password", return_value=True):
            result = auth_service.login(
                uow, LoginRequest(email="juan@test.com", password="Pass123!")
            )

        assert result.access_token is not None
        assert result.refresh_token is not None
        assert result.token_type == "bearer"

    def test_email_no_existe_lanza_401(self):
        uow = make_uow()
        uow.usuarios.get_by_email.return_value = None  # no existe

        with pytest.raises(HTTPException) as exc:
            auth_service.login(
                uow, LoginRequest(email="noexiste@test.com", password="Pass123!")
            )

        assert exc.value.status_code == 401
        assert exc.value.detail["code"] == "INVALID_CREDENTIALS"

    def test_password_incorrecta_lanza_401(self):
        uow = make_uow()
        uow.usuarios.get_by_email.return_value = mock_usuario()

        with patch("app.modules.auth.service.verify_password", return_value=False):
            with pytest.raises(HTTPException) as exc:
                auth_service.login(
                    uow, LoginRequest(email="juan@test.com", password="Incorrecta!")
                )

        assert exc.value.status_code == 401
        assert exc.value.detail["code"] == "INVALID_CREDENTIALS"

    def test_login_no_diferencia_email_vs_password(self):
        """RN-AU08: mismo mensaje de error para email no existe y password incorrecta."""
        uow_sin_email = make_uow()
        uow_sin_email.usuarios.get_by_email.return_value = None

        uow_pass_mal = make_uow()
        uow_pass_mal.usuarios.get_by_email.return_value = mock_usuario()

        with pytest.raises(HTTPException) as exc1:
            auth_service.login(uow_sin_email, LoginRequest(email="x@x.com", password="p"))

        with patch("app.modules.auth.service.verify_password", return_value=False):
            with pytest.raises(HTTPException) as exc2:
                auth_service.login(uow_pass_mal, LoginRequest(email="x@x.com", password="p"))

        assert exc1.value.detail["code"] == exc2.value.detail["code"] == "INVALID_CREDENTIALS"


# ──────────────────────────────────────────────────────────────────────────────
# refresh
# ──────────────────────────────────────────────────────────────────────────────

class TestRefresh:
    def _make_token_obj(self, expired: bool = False):
        t = MagicMock()
        t.usuario_id = 1
        if expired:
            t.expires_at = datetime.utcnow() - timedelta(days=1)
        else:
            t.expires_at = datetime.utcnow() + timedelta(days=7)
        return t

    def test_refresh_exitoso(self):
        uow = make_uow()
        token_obj = self._make_token_obj()
        uow.refresh_tokens.get_active_by_token.return_value = token_obj
        usuario = mock_usuario()
        uow.usuarios.get_by_id.return_value = usuario
        uow.usuarios.get_roles.return_value = [mock_rol("CLIENT")]
        uow.refresh_tokens.add.return_value = MagicMock()

        result = auth_service.refresh(uow, "raw_token_valido")

        assert result.access_token is not None
        uow.refresh_tokens.revoke.assert_called_once_with(token_obj)

    def test_refresh_token_invalido_lanza_401(self):
        uow = make_uow()
        uow.refresh_tokens.get_active_by_token.return_value = None

        with pytest.raises(HTTPException) as exc:
            auth_service.refresh(uow, "token_invalido")

        assert exc.value.status_code == 401
        assert exc.value.detail["code"] == "INVALID_REFRESH_TOKEN"

    def test_refresh_token_expirado_lanza_401(self):
        uow = make_uow()
        token_obj = self._make_token_obj(expired=True)
        uow.refresh_tokens.get_active_by_token.return_value = token_obj

        with pytest.raises(HTTPException) as exc:
            auth_service.refresh(uow, "token_expirado")

        assert exc.value.status_code == 401
        assert exc.value.detail["code"] == "REFRESH_TOKEN_EXPIRED"
        uow.refresh_tokens.revoke.assert_called_once_with(token_obj)

    def test_refresh_rota_el_token(self):
        """El token anterior debe ser revocado y uno nuevo emitido."""
        uow = make_uow()
        token_obj = self._make_token_obj()
        uow.refresh_tokens.get_active_by_token.return_value = token_obj
        uow.usuarios.get_by_id.return_value = mock_usuario()
        uow.usuarios.get_roles.return_value = []
        uow.refresh_tokens.add.return_value = MagicMock()

        auth_service.refresh(uow, "raw_token")

        uow.refresh_tokens.revoke.assert_called_once()
        uow.refresh_tokens.add.assert_called_once()


# ──────────────────────────────────────────────────────────────────────────────
# logout
# ──────────────────────────────────────────────────────────────────────────────

class TestLogout:
    def test_logout_revoca_token(self):
        uow = make_uow()
        token_obj = MagicMock()
        uow.refresh_tokens.get_active_by_token.return_value = token_obj

        auth_service.logout(uow, "raw_token")

        uow.refresh_tokens.revoke.assert_called_once_with(token_obj)

    def test_logout_token_inexistente_no_lanza(self):
        """Si el token no existe, logout silencioso (no rompe)."""
        uow = make_uow()
        uow.refresh_tokens.get_active_by_token.return_value = None

        auth_service.logout(uow, "token_que_no_existe")  # No debe lanzar


# ──────────────────────────────────────────────────────────────────────────────
# get_me
# ──────────────────────────────────────────────────────────────────────────────

class TestGetMe:
    def test_get_me_exitoso(self):
        uow = make_uow()
        usuario = mock_usuario(id=7, email="yo@test.com")
        uow.usuarios.get_by_id.return_value = usuario
        uow.usuarios.get_roles.return_value = [mock_rol("ADMIN")]

        result = auth_service.get_me(uow, 7)

        assert result.id == 7
        assert result.email == "yo@test.com"
        assert result.roles[0].codigo == "ADMIN"

    def test_get_me_usuario_no_encontrado_lanza_404(self):
        uow = make_uow()
        uow.usuarios.get_by_id.return_value = None

        with pytest.raises(HTTPException) as exc:
            auth_service.get_me(uow, 999)

        assert exc.value.status_code == 404
        assert exc.value.detail["code"] == "USER_NOT_FOUND"


# ──────────────────────────────────────────────────────────────────────────────
# forgot_password / reset_password
# ──────────────────────────────────────────────────────────────────────────────

class TestForgotResetPassword:
    def test_forgot_password_email_no_existe_no_revela_nada(self):
        """Por seguridad, si el email no existe, no lanza error (no revela si existe)."""
        uow = make_uow()
        uow.usuarios.get_by_email.return_value = None

        # No debe lanzar excepción
        auth_service.forgot_password(uow, "noexiste@test.com")
        uow.reset_tokens.add.assert_not_called()

    def test_forgot_password_email_existe_crea_token(self):
        uow = make_uow()
        uow.usuarios.get_by_email.return_value = mock_usuario()
        uow.reset_tokens.add.return_value = MagicMock()

        with patch("app.modules.auth.service.httpx.post"):
            auth_service.forgot_password(uow, "juan@test.com")

        uow.reset_tokens.add.assert_called_once()

    def test_reset_password_token_invalido_lanza_400(self):
        uow = make_uow()
        uow.reset_tokens.get_valid_by_token.return_value = None

        with pytest.raises(HTTPException) as exc:
            auth_service.reset_password(uow, "token_invalido", "NuevaClave123!")

        assert exc.value.status_code == 400
        assert exc.value.detail["code"] == "INVALID_RESET_TOKEN"

    def test_reset_password_ok_actualiza_hash(self):
        uow = make_uow()
        token_obj = MagicMock()
        token_obj.usuario_id = 1
        uow.reset_tokens.get_valid_by_token.return_value = token_obj

        usuario = mock_usuario()
        uow.usuarios.get_by_id.return_value = usuario

        with patch("app.modules.auth.service.hash_password", return_value="nuevo_hash"):
            auth_service.reset_password(uow, "token_valido", "NuevaClave123!")

        assert usuario.password_hash == "nuevo_hash"
        uow.reset_tokens.mark_used.assert_called_once_with(token_obj)
