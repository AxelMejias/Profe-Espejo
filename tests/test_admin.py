"""Tests de integración del módulo Admin (doc §5/§13) — gestión de usuarios y roles (RBAC)."""


def _registrar(client, email):
    r = client.post("/api/v1/auth/register", json={
        "nombre": "Test", "apellido": "User", "email": email, "password": "Test1234!",
    })
    # El register puede setear cookie de sesión; la limpiamos para no pisar el Bearer del admin.
    client.cookies.clear()
    return r


def test_listar_usuarios_sin_auth_401(client):
    r = client.get("/api/v1/admin/usuarios")
    assert r.status_code == 401


def test_listar_usuarios_requiere_admin(client, client_headers):
    r = client.get("/api/v1/admin/usuarios", headers=client_headers)
    assert r.status_code == 403


def test_listar_usuarios_admin(client, admin_headers):
    r = client.get("/api/v1/admin/usuarios", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["total"] >= 1


def test_obtener_usuario_por_id(client, admin_headers):
    uid = _registrar(client, "admin_detalle@test.com").json()["id"]
    r = client.get(f"/api/v1/admin/usuarios/{uid}", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["id"] == uid


def test_asignar_y_remover_rol(client, admin_headers):
    uid = _registrar(client, "admin_rol@test.com").json()["id"]
    r = client.post(f"/api/v1/admin/usuarios/{uid}/roles", headers=admin_headers,
                    json={"rol_codigo": "STOCK"})
    assert r.status_code == 201, r.text
    assert any(rol["codigo"] == "STOCK" for rol in r.json()["roles"])
    r = client.delete(f"/api/v1/admin/usuarios/{uid}/roles/STOCK", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert all(rol["codigo"] != "STOCK" for rol in r.json()["roles"])


def test_actualizar_usuario(client, admin_headers):
    uid = _registrar(client, "admin_update@test.com").json()["id"]
    r = client.put(f"/api/v1/admin/usuarios/{uid}", headers=admin_headers,
                   json={"nombre": "Renombrado"})
    assert r.status_code == 200, r.text
    assert r.json()["nombre"] == "Renombrado"


def test_eliminar_usuario(client, admin_headers):
    uid = _registrar(client, "admin_delete@test.com").json()["id"]
    r = client.delete(f"/api/v1/admin/usuarios/{uid}", headers=admin_headers)
    assert r.status_code == 204, r.text


# ── Guard "último admin": el sistema nunca debe quedarse sin administrador ──────

def _admin_seed_id(client, admin_headers) -> int:
    r = client.get("/api/v1/admin/usuarios?rol_codigo=ADMIN&size=100", headers=admin_headers)
    assert r.status_code == 200, r.text
    return next(u["id"] for u in r.json()["items"] if u["email"] == "admin@foodstore.com")


def test_no_se_puede_quitar_rol_admin_al_ultimo_admin(client, admin_headers):
    """RED-04 equivalente: quitar ADMIN al único admin debe rechazarse (403)."""
    admin_id = _admin_seed_id(client, admin_headers)
    r = client.delete(f"/api/v1/admin/usuarios/{admin_id}/roles/ADMIN", headers=admin_headers)
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["code"] == "LAST_ADMIN"


def test_no_se_puede_eliminar_al_ultimo_admin(client, admin_headers):
    """Eliminar (baja lógica) al único admin debe rechazarse (403)."""
    admin_id = _admin_seed_id(client, admin_headers)
    r = client.delete(f"/api/v1/admin/usuarios/{admin_id}", headers=admin_headers)
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["code"] == "LAST_ADMIN"


def test_se_puede_quitar_rol_admin_si_no_es_el_ultimo(client, admin_headers):
    """Triangulación: con 2 admins, quitar el rol a uno SÍ se permite."""
    uid = _registrar(client, "segundo_admin_rol@test.com").json()["id"]
    client.post(f"/api/v1/admin/usuarios/{uid}/roles", headers=admin_headers,
                json={"rol_codigo": "ADMIN"})
    r = client.delete(f"/api/v1/admin/usuarios/{uid}/roles/ADMIN", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert all(rol["codigo"] != "ADMIN" for rol in r.json()["roles"])


def test_se_puede_eliminar_admin_si_no_es_el_ultimo(client, admin_headers):
    """Triangulación: con 2 admins, eliminar a uno SÍ se permite."""
    uid = _registrar(client, "segundo_admin_del@test.com").json()["id"]
    client.post(f"/api/v1/admin/usuarios/{uid}/roles", headers=admin_headers,
                json={"rol_codigo": "ADMIN"})
    r = client.delete(f"/api/v1/admin/usuarios/{uid}", headers=admin_headers)
    assert r.status_code == 204, r.text


# ── Baja con efecto inmediato + soft delete + reactivación ─────────────────────

def _login_bearer(client, email, password="Test1234!") -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    client.cookies.clear()
    return {"Authorization": f"Bearer {token}"}


def test_baja_bloquea_token_existente_de_inmediato(client, admin_headers):
    """Concern #1: dar de baja a un usuario invalida su sesión activa al instante,
    aunque su JWT siga vigente (no puede seguir operando/comprando)."""
    uid = _registrar(client, "baja_inmediata@test.com").json()["id"]
    user_headers = _login_bearer(client, "baja_inmediata@test.com")

    # Con la cuenta activa, el usuario puede operar.
    assert client.get("/api/v1/direcciones/", headers=user_headers).status_code == 200

    # El admin lo da de baja…
    assert client.delete(f"/api/v1/admin/usuarios/{uid}", headers=admin_headers).status_code == 204

    # …y su token deja de funcionar de inmediato.
    r = client.get("/api/v1/direcciones/", headers=user_headers)
    assert r.status_code == 401
    assert r.json()["detail"]["code"] == "USER_INACTIVE"


def test_usuario_dado_de_baja_no_aparece_en_activos_pero_si_en_inactivos(client, admin_headers):
    """Concern #2: la baja es lógica. El usuario sale del listado de activos pero
    sigue consultable con solo_inactivos=true (no es un borrado total)."""
    uid = _registrar(client, "baja_logica@test.com").json()["id"]
    client.delete(f"/api/v1/admin/usuarios/{uid}", headers=admin_headers)

    activos = client.get("/api/v1/admin/usuarios?size=100", headers=admin_headers).json()["items"]
    assert all(u["id"] != uid for u in activos)

    inactivos = client.get("/api/v1/admin/usuarios?solo_inactivos=true&size=100", headers=admin_headers).json()["items"]
    encontrado = next((u for u in inactivos if u["id"] == uid), None)
    assert encontrado is not None and encontrado["deleted_at"] is not None


def test_reactivar_usuario_restaura_acceso(client, admin_headers):
    """Concern #2: reactivar un usuario lo vuelve activo y le devuelve el acceso."""
    uid = _registrar(client, "reactivar@test.com").json()["id"]
    client.delete(f"/api/v1/admin/usuarios/{uid}", headers=admin_headers)

    r = client.patch(f"/api/v1/admin/usuarios/{uid}/reactivar", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["deleted_at"] is None

    # Vuelve a aparecer en activos y puede loguearse/operar de nuevo.
    activos = client.get("/api/v1/admin/usuarios?size=100", headers=admin_headers).json()["items"]
    assert any(u["id"] == uid for u in activos)
    user_headers = _login_bearer(client, "reactivar@test.com")
    assert client.get("/api/v1/direcciones/", headers=user_headers).status_code == 200


def test_reactivar_usuario_activo_da_404(client, admin_headers):
    """Reactivar a alguien que no está dado de baja no tiene sentido → 404."""
    uid = _registrar(client, "ya_activo@test.com").json()["id"]
    r = client.patch(f"/api/v1/admin/usuarios/{uid}/reactivar", headers=admin_headers)
    assert r.status_code == 404, r.text


# ── Búsqueda de usuarios ───────────────────────────────────────────────────────

def test_buscar_usuario_por_email(client, admin_headers):
    _registrar(client, "buscable_unico@test.com")
    r = client.get("/api/v1/admin/usuarios?q=buscable_unico&size=100", headers=admin_headers)
    assert r.status_code == 200, r.text
    emails = [u["email"] for u in r.json()["items"]]
    assert "buscable_unico@test.com" in emails


def test_buscar_usuario_por_nombre(client, admin_headers):
    # El registro crea nombre "Test"; buscamos por ese nombre y debe traer resultados.
    _registrar(client, "buscable_nombre@test.com")
    r = client.get("/api/v1/admin/usuarios?q=Test&size=100", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert any(u["email"] == "buscable_nombre@test.com" for u in r.json()["items"])


def test_buscar_usuario_sin_coincidencias(client, admin_headers):
    r = client.get("/api/v1/admin/usuarios?q=zzz_no_existe_nadie_zzz", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 0


# ── Cambio de rol con efecto inmediato ─────────────────────────────────────────

def test_quitar_rol_admin_corta_acceso_de_inmediato(client, admin_headers):
    """Si a un usuario con sesión activa se le quita el rol ADMIN, pierde el acceso
    a los endpoints de admin al instante, aunque su JWT siga teniendo el rol viejo."""
    uid = _registrar(client, "demote_admin@test.com").json()["id"]
    client.post(f"/api/v1/admin/usuarios/{uid}/roles", headers=admin_headers,
                json={"rol_codigo": "ADMIN"})
    user_headers = _login_bearer(client, "demote_admin@test.com")

    # Con rol ADMIN puede listar usuarios.
    assert client.get("/api/v1/admin/usuarios", headers=user_headers).status_code == 200

    # El admin le quita el rol ADMIN…
    assert client.delete(f"/api/v1/admin/usuarios/{uid}/roles/ADMIN",
                         headers=admin_headers).status_code == 200

    # …y su token deja de tener acceso de admin de inmediato (roles frescos de la BD).
    assert client.get("/api/v1/admin/usuarios", headers=user_headers).status_code == 403
