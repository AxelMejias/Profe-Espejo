"""
test_security.py — Tests para app/core/security.py

Cubre: hash_password, verify_password, create_access_token, decode_access_token.
No requiere DB.
"""
import pytest
from jose import JWTError

from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
)


class TestHashPassword:
    def test_devuelve_string(self):
        result = hash_password("MiPassword123!")
        assert isinstance(result, str)

    def test_hash_distinto_al_plaintext(self):
        plain = "MiPassword123!"
        assert hash_password(plain) != plain

    def test_dos_hashes_distintos_por_salt(self):
        plain = "MiPassword123!"
        assert hash_password(plain) != hash_password(plain)

    def test_longitud_bcrypt(self):
        # bcrypt produce hashes de exactamente 60 caracteres
        result = hash_password("cualquier_clave")
        assert len(result) == 60


class TestVerifyPassword:
    def test_password_correcta(self):
        plain = "Correcta123!"
        hashed = hash_password(plain)
        assert verify_password(plain, hashed) is True

    def test_password_incorrecta(self):
        hashed = hash_password("Correcta123!")
        assert verify_password("Incorrecta456!", hashed) is False

    def test_string_vacio_no_matchea(self):
        hashed = hash_password("AlgunaPassword!")
        assert verify_password("", hashed) is False


class TestCreateDecodeAccessToken:
    def test_encode_decode_roundtrip(self):
        payload = {"sub": "42", "email": "test@test.com", "roles": ["CLIENT"]}
        token = create_access_token(payload)
        decoded = decode_access_token(token)

        assert decoded["sub"] == "42"
        assert decoded["email"] == "test@test.com"
        assert decoded["roles"] == ["CLIENT"]

    def test_token_es_string(self):
        token = create_access_token({"sub": "1"})
        assert isinstance(token, str)
        # JWT tiene 3 partes separadas por puntos
        assert len(token.split(".")) == 3

    def test_token_invalido_lanza_jwterror(self):
        with pytest.raises(JWTError):
            decode_access_token("esto.no.es.un.jwt.valido")

    def test_token_tampered_lanza_jwterror(self):
        token = create_access_token({"sub": "1"})
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(JWTError):
            decode_access_token(tampered)

    def test_payload_contiene_exp(self):
        token = create_access_token({"sub": "1"})
        decoded = decode_access_token(token)
        assert "exp" in decoded
