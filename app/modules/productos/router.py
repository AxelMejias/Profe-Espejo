from io import BytesIO
from typing import Annotated, Optional
import math
from decimal import Decimal
from fastapi import APIRouter, Depends, Query, Path, Body, UploadFile, File, status, HTTPException  # noqa: F401
from fastapi.responses import StreamingResponse
import openpyxl

from app.modules.productos.schemas import (
    ProductoCreate, ProductoUpdate, ProductoRead, PaginatedProductos,
)
from app.modules.productos import service
from app.core.dependencies import require_role
from app.core.unit_of_work import UnitOfWork


router = APIRouter(prefix="/api/v1/productos", tags=["Productos"])

_PUBLICO        = Depends(require_role(["ADMIN", "STOCK", "PEDIDOS", "CLIENT"]))
_DISPONIBILIDAD = Depends(require_role(["ADMIN", "STOCK"]))   # toggle disponibilidad
_ADMIN          = Depends(require_role(["ADMIN"]))             # crear, editar, borrar, importar, reactivar

_BOOL_MAP = {"TRUE", "VERDADERO", "SI", "SÍ", "S", "1"}


@router.get("/exportar", summary="Exportar productos activos a Excel")
def exportar_productos(_=_ADMIN):
    rows = []
    with UnitOfWork() as uow:
        items, _ = uow.productos.get_all(solo_disponibles=False, page=1, size=10000)
        for prod in items:
            cats = ", ".join(c.nombre for c in prod.categorias)
            links = uow.productos.get_ingrediente_links(prod.id)
            insumos_parts = []
            for link in links:
                ing = uow.ingredientes.get_by_id(link.ingrediente_id)
                if ing:
                    insumos_parts.append(f"{ing.nombre}:{link.cantidad}")
            rows.append([
                prod.id, prod.nombre, prod.descripcion or "",
                float(prod.precio), float(prod.margen_ganancia) * 100,
                "Sí" if prod.disponible else "No",
                cats, ", ".join(insumos_parts),
            ])

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Productos"
    ws.append(["ID", "Nombre", "Descripción", "Precio", "Margen (%)", "Disponible", "Categorías", "Insumos"])
    for row in rows:
        ws.append(row)
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=productos.xlsx"},
    )


@router.get("/plantilla", summary="Descargar plantilla Excel para importar productos")
def descargar_plantilla(_=_ADMIN):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Productos"
    ws.append([
        "Nombre", "Descripcion", "Margen Ganancia (ej: 0.30)",
        "Disponible", "Categorias (nombres separados por coma)",
        "Insumos (nombre:cantidad separados por coma)",
    ])
    ws.append([
        "Hamburguesa Clásica", "", "0.30", "TRUE",
        "Comidas rápidas", "Carne:0.2,Pan:1,Lechuga:0.05",
    ])
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=plantilla_productos.xlsx"},
    )


@router.post("/importar", summary="Importar productos desde Excel")
def importar_productos(archivo: UploadFile = File(...), _=_ADMIN):
    from app.modules.productos.model import Producto
    from app.core.links import ProductoIngrediente
    from sqlmodel import select

    contents = archivo.file.read()
    wb = openpyxl.load_workbook(BytesIO(contents), data_only=True)
    ws = wb.active

    creados = 0
    omitidos = 0
    errores = []

    for idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if not row or all(v is None for v in row):
            continue
        try:
            nombre = str(row[0]).strip() if row[0] is not None else ""
            descripcion = str(row[1]).strip() if len(row) > 1 and row[1] is not None else None
            margen_raw = row[2] if len(row) > 2 and row[2] is not None else None
            disponible_raw = str(row[3]).upper().strip() if len(row) > 3 and row[3] is not None else "TRUE"
            cats_raw = str(row[4]).strip() if len(row) > 4 and row[4] is not None else ""
            insumos_raw = str(row[5]).strip() if len(row) > 5 and row[5] is not None else ""

            if not nombre:
                errores.append({"fila": idx, "nombre": "", "motivo": "Nombre requerido"})
                continue
            if margen_raw is None:
                errores.append({"fila": idx, "nombre": nombre, "motivo": "Margen de ganancia requerido"})
                continue
            if not insumos_raw:
                errores.append({"fila": idx, "nombre": nombre, "motivo": "Insumos requeridos"})
                continue

            margen = Decimal(str(margen_raw))
            disponible = disponible_raw in _BOOL_MAP

            # Parsear insumos: "nombre:cantidad, nombre:cantidad"
            insumo_pairs = []
            for par in insumos_raw.split(","):
                par = par.strip()
                if not par:
                    continue
                if ":" not in par:
                    errores.append({"fila": idx, "nombre": nombre, "motivo": f"Formato de insumo inválido: '{par}'"})
                    break
                nombre_ing, cantidad_str = par.rsplit(":", 1)
                insumo_pairs.append((nombre_ing.strip(), Decimal(cantidad_str.strip())))
            else:
                if not insumo_pairs:
                    errores.append({"fila": idx, "nombre": nombre, "motivo": "Debe tener al menos un insumo"})
                    continue

                with UnitOfWork() as uow:
                    if uow.productos.get_by_nombre(nombre):
                        omitidos += 1
                        continue

                    insumos_orm = []
                    cantidades = {}
                    fallo = False
                    for nombre_ing, cantidad in insumo_pairs:
                        ing = uow.ingredientes.get_by_nombre(nombre_ing)
                        if not ing:
                            errores.append({"fila": idx, "nombre": nombre, "motivo": f"Ingrediente '{nombre_ing}' no encontrado"})
                            fallo = True
                            break
                        cantidades[ing.id] = cantidad
                        insumos_orm.append(ing)

                    if fallo:
                        continue

                    costo = sum(ing.costo_unitario * cantidades[ing.id] for ing in insumos_orm)
                    precio = (costo * (1 + margen)).quantize(Decimal("0.01"))

                    producto = Producto(
                        nombre=nombre,
                        descripcion=descripcion or None,
                        precio=precio,
                        margen_ganancia=margen,
                        disponible=disponible,
                    )
                    uow.productos.add(producto)

                    for ing in insumos_orm:
                        uow.productos.add_ingrediente_link(
                            producto_id=producto.id,
                            ingrediente_id=ing.id,
                            cantidad=float(cantidades[ing.id]),
                        )

                    if cats_raw:
                        nombres_cats = [c.strip() for c in cats_raw.split(",") if c.strip()]
                        cats = [c for n in nombres_cats for c in [uow.categorias.get_by_nombre(n)] if c]
                        if cats:
                            producto.categorias = cats
                            uow.productos.add(producto)

                    creados += 1
        except Exception as e:
            nombre_str = str(row[0]) if row and row[0] is not None else ""
            errores.append({"fila": idx, "nombre": nombre_str, "motivo": str(e)})

    return {"creados": creados, "omitidos": omitidos, "errores": errores}



@router.get("/", response_model=PaginatedProductos, summary="Listar productos")
def listar_productos(
    nombre:           Annotated[Optional[str],   Query(max_length=100)] = None,
    precio_min:       Annotated[Optional[float], Query(ge=0)]           = None,
    precio_max:       Annotated[Optional[float], Query(ge=0)]           = None,
    categoria_id:     Annotated[Optional[int],   Query(ge=1)]           = None,
    solo_disponibles: Annotated[bool, Query()]                          = True,
    solo_destacados:  Annotated[bool, Query()]                          = False,
    page:             Annotated[int, Query(ge=1)]                       = 1,
    size:             Annotated[int, Query(ge=1, le=100)]               = 20,
    _=_PUBLICO,
):
    with UnitOfWork() as uow:
        return service.get_all(
            uow, nombre=nombre, precio_min=precio_min, precio_max=precio_max,
            categoria_id=categoria_id, solo_disponibles=solo_disponibles,
            solo_destacados=solo_destacados, page=page, size=size,
        )


@router.get("/inactivos", response_model=PaginatedProductos, summary="Listar productos inactivos")
def listar_productos_inactivos(
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    _=_ADMIN,
):
    with UnitOfWork() as uow:
        items, total = uow.productos.get_all_inactivos(page=page, size=size)
        return PaginatedProductos(
            items=[service._build_response(uow, p) for p in items],
            total=total, page=page, size=size,
            pages=math.ceil(total / size) if total else 0,
        )


@router.get("/{producto_id}", response_model=ProductoRead, summary="Obtener producto por ID")
def obtener_producto(producto_id: Annotated[int, Path(ge=1)], _=_PUBLICO):
    with UnitOfWork() as uow:
        return service.get_by_id(uow, producto_id)


@router.post("/", response_model=ProductoRead, status_code=status.HTTP_201_CREATED, summary="Crear producto")
def crear_producto(data: ProductoCreate, _=_ADMIN):
    with UnitOfWork() as uow:
        return service.create(uow, data)


@router.put("/{producto_id}", response_model=ProductoRead, summary="Actualizar producto")
def actualizar_producto(
    producto_id: Annotated[int, Path(ge=1)],
    data: ProductoUpdate,
    _=_ADMIN,
):
    with UnitOfWork() as uow:
        return service.update(uow, producto_id, data)


@router.patch("/{producto_id}/reactivar", response_model=ProductoRead, summary="Reactivar producto inactivo")
def reactivar_producto(producto_id: Annotated[int, Path(ge=1)], _=_ADMIN):
    with UnitOfWork() as uow:
        return service.reactivar(uow, producto_id)


@router.patch("/{producto_id}/disponibilidad", response_model=ProductoRead, summary="Toggle disponibilidad")
def toggle_disponibilidad(
    producto_id: Annotated[int, Path(ge=1)],
    disponible: bool = Body(..., embed=True),
    _=_DISPONIBILIDAD,
):
    with UnitOfWork() as uow:
        return service.toggle_disponibilidad(uow, producto_id, disponible)


@router.patch("/{producto_id}/destacar", response_model=ProductoRead, summary="Toggle destacado en Home")
def toggle_destacado(
    producto_id: Annotated[int, Path(ge=1)],
    destacado: bool = Body(..., embed=True),
    _=_ADMIN,
):
    with UnitOfWork() as uow:
        return service.toggle_destacado(uow, producto_id, destacado)


@router.delete("/{producto_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Baja lógica de producto")
def eliminar_producto(producto_id: Annotated[int, Path(ge=1)], _=_ADMIN):
    with UnitOfWork() as uow:
        service.delete(uow, producto_id)
