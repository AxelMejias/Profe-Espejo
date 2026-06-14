"""Tests de integración del módulo Uploads (doc §10/§13) — RBAC y validaciones."""


def test_upload_sin_auth_401(client):
    r = client.post("/api/v1/uploads/imagen",
                    files={"archivo": ("foto.png", b"datos", "image/png")})
    assert r.status_code == 401


def test_upload_requiere_admin(client, client_headers):
    r = client.post("/api/v1/uploads/imagen", headers=client_headers,
                    files={"archivo": ("foto.png", b"datos", "image/png")})
    assert r.status_code == 403


def test_upload_tipo_invalido_rechazado(client, admin_headers):
    """Tipo MIME no permitido → 400 (o 503 si Cloudinary no está configurado en el entorno)."""
    r = client.post("/api/v1/uploads/imagen", headers=admin_headers,
                    files={"archivo": ("doc.txt", b"texto plano", "text/plain")})
    assert r.status_code in (400, 503), r.text


def test_delete_imagen_requiere_admin(client, client_headers):
    r = client.delete("/api/v1/uploads/imagen/foo", headers=client_headers)
    assert r.status_code == 403
