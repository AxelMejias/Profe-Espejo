"""Tests de integración del módulo Direcciones (doc §5/§13) — CRUD, principal y ownership."""


def _crear(client, headers, alias="Casa", principal=False):
    return client.post("/api/v1/direcciones/", headers=headers, json={
        "alias": alias, "linea1": "Calle Falsa 123", "ciudad": "Springfield",
        "es_principal": principal,
    })


def test_direcciones_sin_auth_401(client):
    r = client.get("/api/v1/direcciones/")
    assert r.status_code == 401


def test_crear_direccion(client, client_headers):
    r = _crear(client, client_headers, alias="Casa")
    assert r.status_code == 201, r.text
    assert r.json()["linea1"] == "Calle Falsa 123"


def test_listar_mis_direcciones(client, client_headers):
    _crear(client, client_headers, alias="Listado")
    r = client.get("/api/v1/direcciones/", headers=client_headers)
    assert r.status_code == 200, r.text
    assert r.json()["total"] >= 1


def test_obtener_direccion_por_id(client, client_headers):
    did = _crear(client, client_headers, alias="Detalle").json()["id"]
    r = client.get(f"/api/v1/direcciones/{did}", headers=client_headers)
    assert r.status_code == 200, r.text
    assert r.json()["id"] == did


def test_marcar_principal(client, client_headers):
    did = _crear(client, client_headers, alias="Principal").json()["id"]
    r = client.patch(f"/api/v1/direcciones/{did}/principal", headers=client_headers)
    assert r.status_code == 200, r.text
    assert r.json()["es_principal"] is True


def test_actualizar_direccion(client, client_headers):
    did = _crear(client, client_headers, alias="Update").json()["id"]
    r = client.put(f"/api/v1/direcciones/{did}", headers=client_headers,
                   json={"ciudad": "Nueva Ciudad"})
    assert r.status_code == 200, r.text
    assert r.json()["ciudad"] == "Nueva Ciudad"


def test_eliminar_direccion(client, client_headers):
    did = _crear(client, client_headers, alias="Borrar").json()["id"]
    r = client.delete(f"/api/v1/direcciones/{did}", headers=client_headers)
    assert r.status_code == 204, r.text
