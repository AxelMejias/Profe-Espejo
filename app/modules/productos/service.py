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

from app.core.links import ProductoIngrediente
from app.modules.categorias.model import Categoria
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
    from sqlmodel import select

    links = list(uow.session.exec(
        select(ProductoIngrediente).where(
            ProductoIngrediente.producto_id == producto.id
        )
    ).all())

    insumos_read = []
    costo_total = Decimal("0.00")

    for link in links:
        ing: Optional[Ingrediente] = uow.session.get(Ingrediente, link.ingrediente_id)
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

    return ProductoRead(
        id=producto.id,
        nombre=producto.nombre,
        descripcion=producto.descripcion,
        precio=producto.precio,
        margen_ganancia=producto.margen_ganancia,
        costo_total_insumos=costo_total,
        disponible=producto.disponible,
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

def get_all(uow, nombre: Optional[str] = None, page: int = 1, size: int = 20) -> PaginatedProductos:
    items, total = uow.productos.get_all(nombre=nombre, page=page, size=size)
    return PaginatedProductos(
        items=[_build_response(uow, p) for p in items],
        total=total, page=page, size=size,
        pages=math.ceil(total / size) if total else 0,
    )


def get_by_id(uow, producto_id: int) -> ProductoRead:
    producto = uow.productos.get_by_id(producto_id)
    if not producto:
        _problem("PRODUCTO_NOT_FOUND", f"Producto {producto_id} no encontrado", status.HTTP_404_NOT_FOUND)
    return _build_response(uow, producto)


def create(uow, data: ProductoCreate) -> ProductoRead:
    from sqlmodel import select

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


    producto = Producto(
        nombre=data.nombre,
        descripcion=data.descripcion,
        precio=precio,
        margen_ganancia=data.margen_ganancia,
        disponible=data.disponible,
    )
    uow.productos.add(producto)   # flush interno → genera el ID

    for ing in insumos_orm:
        link = ProductoIngrediente(
            producto_id=producto.id,
            ingrediente_id=ing.id,
            cantidad=float(cantidades[ing.id]),
        )
        uow.session.add(link)
    uow.session.flush()

    if data.categoria_ids:
        cats = list(uow.session.exec(
            select(Categoria).where(Categoria.id.in_(data.categoria_ids))
        ).all())
        producto.categorias = cats
        uow.session.add(producto)
        uow.session.flush()

    return _build_response(uow, producto)


def update(uow, producto_id: int, data: ProductoUpdate) -> ProductoRead:
    from sqlmodel import select, delete as sql_delete

    producto = uow.productos.get_by_id(producto_id)
    if not producto:
        _problem("PRODUCTO_NOT_FOUND", f"Producto {producto_id} no encontrado", status.HTTP_404_NOT_FOUND)

    for field in ("nombre", "descripcion", "disponible"):
        val = getattr(data, field)
        if val is not None:
            setattr(producto, field, val)

    if data.insumos is not None:
        uow.session.exec(
            sql_delete(ProductoIngrediente).where(
                ProductoIngrediente.producto_id == producto_id
            )
        )
        uow.session.flush()

        margen = data.margen_ganancia if data.margen_ganancia is not None else producto.margen_ganancia
        cantidades: dict[int, Decimal] = {}
        insumos_orm: list[Ingrediente] = []
        for item in data.insumos:
            ing = uow.ingredientes.get_by_id(item.ingrediente_id)
            if not ing:
                _problem("INSUMO_NOT_FOUND", f"Insumo {item.ingrediente_id} no encontrado", status.HTTP_404_NOT_FOUND)
            cantidades[ing.id] = item.cantidad
            insumos_orm.append(ing)
            uow.session.add(ProductoIngrediente(
                producto_id=producto_id,
                ingrediente_id=ing.id,
                cantidad=float(item.cantidad),
            ))
        producto.margen_ganancia = margen
        producto.precio = _calcular_precio(insumos_orm, cantidades, margen)
        uow.session.flush()

    elif data.margen_ganancia is not None:
        links = list(uow.session.exec(
            select(ProductoIngrediente).where(ProductoIngrediente.producto_id == producto_id)
        ).all())
        cantidades = {l.ingrediente_id: Decimal(str(l.cantidad)) for l in links}
        insumos_orm = [uow.session.get(Ingrediente, iid) for iid in cantidades]
        producto.margen_ganancia = data.margen_ganancia
        producto.precio = _calcular_precio(insumos_orm, cantidades, data.margen_ganancia)

    if data.categoria_ids is not None:
        cats = list(uow.session.exec(
            select(Categoria).where(Categoria.id.in_(data.categoria_ids))
        ).all())
        producto.categorias = cats

    producto.updated_at = datetime.utcnow()
    uow.session.add(producto)
    uow.session.flush()
    return _build_response(uow, producto)


def toggle_disponibilidad(uow, producto_id: int, disponible: bool) -> ProductoRead:
    producto = uow.productos.get_by_id(producto_id)
    if not producto:
        _problem("PRODUCTO_NOT_FOUND", f"Producto {producto_id} no encontrado", status.HTTP_404_NOT_FOUND)
    producto.disponible = disponible
    producto.updated_at = datetime.utcnow()
    uow.session.add(producto)
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
    uow.session.add(producto)
    return _build_response(uow, producto)