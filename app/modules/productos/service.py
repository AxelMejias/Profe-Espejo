"""
Service de Productos — Parcial 3.
Creación transaccional maestro-detalle con cálculo de precio por insumos.
Regla: NO crea su propio UoW. Recibe `uow` del router.
"""
import math
from datetime import datetime
from decimal import Decimal
from typing import Optional
from fastapi import HTTPException, status

from app.modules.ingredientes.model import Ingrediente
from app.modules.productos.model import Producto
from app.modules.productos.schemas import (
    ProductoCreate, ProductoUpdate, ProductoRead,
    PaginatedProductos, CategoriaSimple, InsumoEnProductoRead,
)


def _problem(code: str, detail: str, http_status: int):
    raise HTTPException(
        status_code=http_status,
        detail={"detail": detail, "code": code, "timestamp": datetime.utcnow().isoformat()},
    )


def _build_response(uow, producto: Producto) -> ProductoRead:
    links = uow.productos.get_ingrediente_links(producto.id)

    insumos_read = []
    costo_total = Decimal("0.00")

    for link in links:
        ing: Optional[Ingrediente] = uow.ingredientes.get_by_id(link.ingrediente_id)
        if not ing:
            continue
        subtotal = Decimal(str(link.cantidad)) * ing.costo_unitario
        costo_total += subtotal
        insumos_read.append(InsumoEnProductoRead(
            ingrediente_id=ing.id,
            nombre=ing.nombre,
            cantidad=Decimal(str(link.cantidad)),
            unidad_medida=ing.unidad_medida,
            costo_unitario=ing.costo_unitario,
            subtotal=subtotal,
            stock_actual=ing.stock_cantidad,
            es_producto_terminado=ing.es_producto_terminado,
        ))

    categorias_read = [
        CategoriaSimple(id=c.id, nombre=c.nombre, parent_id=c.parent_id)
        for c in producto.categorias
    ]

    unidad_simbolo = None
    if producto.unidad_venta_id:
        unidad = uow.unidades.get_by_id(producto.unidad_venta_id)
        unidad_simbolo = unidad.simbolo if unidad else None

    return ProductoRead(
        id=producto.id,
        nombre=producto.nombre,
        descripcion=producto.descripcion,
        image_url=producto.image_url,
        precio=producto.precio,
        margen_ganancia=producto.margen_ganancia,
        costo_total_insumos=costo_total,
        disponible=producto.disponible,
        destacado=producto.destacado,
        unidad_venta_id=producto.unidad_venta_id,
        unidad_venta_simbolo=unidad_simbolo,
        categorias=categorias_read,
        insumos=insumos_read,
        created_at=producto.created_at,
        updated_at=producto.updated_at,
    )


def _calcular_precio(insumos: list[Ingrediente], cantidades: dict[int, Decimal], margen: Decimal) -> Decimal:
    """precio = sum(costo_unitario * cantidad) * (1 + margen)"""
    costo = sum(ing.costo_unitario * cantidades[ing.id] for ing in insumos)
    return (costo * (1 + margen)).quantize(Decimal("0.01"))


#CRUD

def get_all(
    uow,
    nombre: Optional[str] = None,
    precio_min: Optional[float] = None,
    precio_max: Optional[float] = None,
    categoria_id: Optional[int] = None,
    solo_disponibles: bool = True,
    solo_destacados: bool = False,
    page: int = 1,
    size: int = 20,
) -> PaginatedProductos:
    categoria_ids = uow.categorias.get_descendant_ids(categoria_id) if categoria_id else None
    items, total = uow.productos.get_all(
        nombre=nombre,
        precio_min=precio_min,
        precio_max=precio_max,
        categoria_ids=categoria_ids,
        solo_disponibles=solo_disponibles,
        solo_destacados=solo_destacados,
        page=page,
        size=size,
    )
    return PaginatedProductos(
        items=[_build_response(uow, p) for p in items],
        total=total, page=page, size=size,
        pages=math.ceil(total / size) if total else 0,
    )


def toggle_destacado(uow, producto_id: int, destacar: bool) -> ProductoRead:
    producto = uow.productos.get_by_id(producto_id)
    if not producto:
        _problem("PRODUCTO_NOT_FOUND", f"Producto {producto_id} no encontrado", status.HTTP_404_NOT_FOUND)
    if destacar and not producto.destacado:
        total_destacados = uow.productos.count_destacados()
        if total_destacados >= 4:
            _problem(
                "DESTACADOS_LIMIT",
                "Ya hay 4 productos destacados. Quitá uno antes de destacar otro.",
                status.HTTP_409_CONFLICT,
            )
    producto.destacado = destacar
    producto.updated_at = datetime.utcnow()
    uow.productos.add(producto)
    return _build_response(uow, producto)


def get_by_id(uow, producto_id: int) -> ProductoRead:
    producto = uow.productos.get_by_id(producto_id)
    if not producto:
        _problem("PRODUCTO_NOT_FOUND", f"Producto {producto_id} no encontrado", status.HTTP_404_NOT_FOUND)
    return _build_response(uow, producto)


def create(uow, data: ProductoCreate) -> ProductoRead:
    if uow.productos.get_by_nombre(data.nombre):
        _problem("NOMBRE_CONFLICT", f"Ya existe un producto '{data.nombre}'", status.HTTP_409_CONFLICT)

    ids_vistos = set()
    for item in data.insumos:
        if item.ingrediente_id in ids_vistos:
            _problem("INSUMO_DUPLICADO", f"El insumo {item.ingrediente_id} aparece más de una vez", status.HTTP_400_BAD_REQUEST)
        ids_vistos.add(item.ingrediente_id)

    cantidades: dict[int, Decimal] = {}
    insumos_orm: list[Ingrediente] = []
    for item in data.insumos:
        ing = uow.ingredientes.get_by_id(item.ingrediente_id)
        if not ing:
            _problem("INSUMO_NOT_FOUND", f"Insumo {item.ingrediente_id} no encontrado", status.HTTP_404_NOT_FOUND)
        cantidades[ing.id] = item.cantidad
        insumos_orm.append(ing)

    precio = _calcular_precio(insumos_orm, cantidades, data.margen_ganancia)

    if data.unidad_venta_id and not uow.unidades.get_by_id(data.unidad_venta_id):
        _problem("UNIDAD_NOT_FOUND", f"Unidad de medida {data.unidad_venta_id} no encontrada", status.HTTP_404_NOT_FOUND)

    producto = Producto(
        nombre=data.nombre,
        descripcion=data.descripcion,
        image_url=data.image_url,
        precio=precio,
        margen_ganancia=data.margen_ganancia,
        disponible=data.disponible,
        unidad_venta_id=data.unidad_venta_id,
    )
    uow.productos.add(producto)

    for ing in insumos_orm:
        uow.productos.add_ingrediente_link(
            producto_id=producto.id,
            ingrediente_id=ing.id,
            cantidad=float(cantidades[ing.id]),
        )

    if data.categoria_ids:
        cats = uow.categorias.get_by_ids(data.categoria_ids)
        producto.categorias = cats
        uow.productos.add(producto)

    return _build_response(uow, producto)


def update(uow, producto_id: int, data: ProductoUpdate) -> ProductoRead:
    producto = uow.productos.get_by_id(producto_id)
    if not producto:
        _problem("PRODUCTO_NOT_FOUND", f"Producto {producto_id} no encontrado", status.HTTP_404_NOT_FOUND)

    for field in ("nombre", "descripcion", "image_url", "disponible"):
        val = getattr(data, field)
        if val is not None:
            setattr(producto, field, val)

    if data.unidad_venta_id is not None:
        if not uow.unidades.get_by_id(data.unidad_venta_id):
            _problem("UNIDAD_NOT_FOUND", f"Unidad de medida {data.unidad_venta_id} no encontrada", status.HTTP_404_NOT_FOUND)
        producto.unidad_venta_id = data.unidad_venta_id

    if data.insumos is not None:
        uow.productos.delete_ingrediente_links(producto_id)

        margen = data.margen_ganancia if data.margen_ganancia is not None else producto.margen_ganancia
        cantidades: dict[int, Decimal] = {}
        insumos_orm: list[Ingrediente] = []
        for item in data.insumos:
            ing = uow.ingredientes.get_by_id(item.ingrediente_id)
            if not ing:
                _problem("INSUMO_NOT_FOUND", f"Insumo {item.ingrediente_id} no encontrado", status.HTTP_404_NOT_FOUND)
            cantidades[ing.id] = item.cantidad
            insumos_orm.append(ing)
            uow.productos.add_ingrediente_link(
                producto_id=producto_id,
                ingrediente_id=ing.id,
                cantidad=float(item.cantidad),
            )
        producto.margen_ganancia = margen
        producto.precio = _calcular_precio(insumos_orm, cantidades, margen)

    elif data.margen_ganancia is not None:
        links = uow.productos.get_ingrediente_links(producto_id)
        cantidades = {l.ingrediente_id: Decimal(str(l.cantidad)) for l in links}
        insumos_orm = [uow.ingredientes.get_by_id(iid) for iid in cantidades]
        producto.margen_ganancia = data.margen_ganancia
        producto.precio = _calcular_precio(insumos_orm, cantidades, data.margen_ganancia)

    if data.categoria_ids is not None:
        cats = uow.categorias.get_by_ids(data.categoria_ids)
        producto.categorias = cats

    producto.updated_at = datetime.utcnow()
    uow.productos.add(producto)
    return _build_response(uow, producto)


def toggle_disponibilidad(uow, producto_id: int, disponible: bool) -> ProductoRead:
    producto = uow.productos.get_by_id(producto_id)
    if not producto:
        _problem("PRODUCTO_NOT_FOUND", f"Producto {producto_id} no encontrado", status.HTTP_404_NOT_FOUND)
    producto.disponible = disponible
    producto.updated_at = datetime.utcnow()
    uow.productos.add(producto)
    return _build_response(uow, producto)


def delete(uow, producto_id: int) -> None:
    producto = uow.productos.get_by_id(producto_id)
    if not producto:
        _problem("PRODUCTO_NOT_FOUND", f"Producto {producto_id} no encontrado", status.HTTP_404_NOT_FOUND)
    uow.productos.soft_delete(producto)


def reactivar(uow, producto_id: int) -> ProductoRead:
    producto = uow.productos.get_by_id_inactivo(producto_id)
    if not producto:
        _problem("PRODUCTO_NOT_FOUND", f"Producto {producto_id} no encontrado o ya está activo", status.HTTP_404_NOT_FOUND)
    producto.deleted_at = None
    producto.disponible = True
    producto.updated_at = datetime.utcnow()
    uow.productos.add(producto)
    return _build_response(uow, producto)
