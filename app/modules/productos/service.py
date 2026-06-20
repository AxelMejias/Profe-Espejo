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
    AsociarIngredienteRequest, ProductoIngredienteRead,
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
        activo = ing is not None
        if ing is None:
            # Ingrediente dado de baja: NO lo quitamos de la receta. Lo dejamos visible
            # como insumo no disponible y con stock 0, para que el producto figure "sin
            # stock" (stock_disponible = 0) hasta que se reactive el insumo o se actualice
            # la receta. El costo se conserva: el precio del producto no baja artificialmente.
            ing = uow.ingredientes.get_by_id_inactivo(link.ingrediente_id)
            if ing is None:
                continue
        cantidad = Decimal(str(link.cantidad))
        subtotal = cantidad * ing.costo_unitario
        costo_total += subtotal
        insumos_read.append(InsumoEnProductoRead(
            ingrediente_id=ing.id,
            nombre=ing.nombre,
            cantidad=cantidad,
            unidad_medida=ing.unidad_medida,
            costo_unitario=ing.costo_unitario,
            subtotal=subtotal,
            stock_actual=ing.stock_cantidad if activo else Decimal("0"),
            es_producto_terminado=ing.es_producto_terminado,
            activo=activo,
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
        imagenes_url=producto.imagenes_url or [],
        precio_base=producto.precio_base,
        margen_ganancia=producto.margen_ganancia,
        costo_total_insumos=costo_total,
        stock_cantidad=producto.stock_cantidad,
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


def recalcular_precios_por_ingrediente(uow, ingrediente_id: int) -> list[int]:
    """
    Recalcula y persiste el precio_base de todos los productos activos que usan el
    ingrediente como insumo. Se llama cuando cambia el costo_unitario del ingrediente:
    como precio = costo_insumos * (1 + margen), una suba del costo debe reflejarse en
    el precio final del producto. Devuelve los IDs de los productos modificados.
    """
    afectados: list[int] = []
    for producto in uow.productos.get_por_ingrediente(ingrediente_id):
        links = uow.productos.get_ingrediente_links(producto.id)
        cantidades = {l.ingrediente_id: Decimal(str(l.cantidad)) for l in links}
        insumos_orm = [
            ing for iid in cantidades if (ing := uow.ingredientes.get_by_id(iid)) is not None
        ]
        if not insumos_orm:
            continue
        nuevo_precio = _calcular_precio(insumos_orm, cantidades, producto.margen_ganancia)
        if nuevo_precio != producto.precio_base:
            producto.precio_base = nuevo_precio
            producto.updated_at = datetime.utcnow()
            uow.productos.add(producto)
            afectados.append(producto.id)
    return afectados


def _resolver_unidad_id(uow, unidad_texto: str) -> int:
    """Resuelve la unidad de medida de la receta (NN) a partir de la unidad del
    insumo (texto libre). Matchea por símbolo o nombre; si no, cae a 'ud'."""
    t = (unidad_texto or "").strip().lower()
    unidades = uow.unidades.get_all()
    for u in unidades:
        if u.simbolo.lower() == t or u.nombre.lower() == t:
            return u.id
    fallback = uow.unidades.get_by_simbolo("ud") or (unidades[0] if unidades else None)
    if not fallback:
        _problem("UNIDAD_NOT_FOUND", "No hay unidades de medida cargadas (correr el seed)", status.HTTP_500_INTERNAL_SERVER_ERROR)
    return fallback.id


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
        imagenes_url=data.imagenes_url,
        precio_base=precio,
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
            unidad_medida_id=_resolver_unidad_id(uow, ing.unidad_medida),
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

    for field in ("nombre", "descripcion", "imagenes_url", "disponible"):
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
            # get_by_id_any: permite conservar en la receta un insumo dado de baja
            # (el form de edición lo manda si el admin no lo quitó). Solo 404 si el
            # ingrediente no existe en absoluto.
            ing = uow.ingredientes.get_by_id_any(item.ingrediente_id)
            if not ing:
                _problem("INSUMO_NOT_FOUND", f"Insumo {item.ingrediente_id} no encontrado", status.HTTP_404_NOT_FOUND)
            cantidades[ing.id] = item.cantidad
            insumos_orm.append(ing)
            uow.productos.add_ingrediente_link(
                producto_id=producto_id,
                ingrediente_id=ing.id,
                cantidad=float(item.cantidad),
                unidad_medida_id=_resolver_unidad_id(uow, ing.unidad_medida),
            )
        producto.margen_ganancia = margen
        producto.precio_base = _calcular_precio(insumos_orm, cantidades, margen)

    elif data.margen_ganancia is not None:
        links = uow.productos.get_ingrediente_links(producto_id)
        cantidades = {l.ingrediente_id: Decimal(str(l.cantidad)) for l in links}
        # get_by_id_any: incluir insumos dados de baja para no romper el cálculo si
        # la receta tiene un ingrediente discontinuado.
        insumos_orm = [
            ing for iid in cantidades if (ing := uow.ingredientes.get_by_id_any(iid)) is not None
        ]
        producto.margen_ganancia = data.margen_ganancia
        producto.precio_base = _calcular_precio(insumos_orm, cantidades, data.margen_ganancia)

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


def set_imagenes(uow, producto_id: int, imagenes_url: list[str]) -> ProductoRead:
    """Reemplaza la lista de imágenes del producto (doc §5.2 PATCH /imagenes)."""
    producto = uow.productos.get_by_id(producto_id)
    if not producto:
        _problem("PRODUCTO_NOT_FOUND", f"Producto {producto_id} no encontrado", status.HTTP_404_NOT_FOUND)
    producto.imagenes_url = imagenes_url
    producto.updated_at = datetime.utcnow()
    uow.productos.add(producto)
    return _build_response(uow, producto)


def listar_ingredientes(uow, producto_id: int) -> list[InsumoEnProductoRead]:
    """Lista los insumos asociados a un producto (doc §5.2 GET /ingredientes)."""
    producto = uow.productos.get_by_id(producto_id)
    if not producto:
        _problem("PRODUCTO_NOT_FOUND", f"Producto {producto_id} no encontrado", status.HTTP_404_NOT_FOUND)
    insumos = []
    for link in uow.productos.get_ingrediente_links(producto_id):
        ing = uow.ingredientes.get_by_id(link.ingrediente_id)
        activo = ing is not None
        if ing is None:
            ing = uow.ingredientes.get_by_id_inactivo(link.ingrediente_id)
            if ing is None:
                continue
        cantidad = Decimal(str(link.cantidad))
        insumos.append(InsumoEnProductoRead(
            ingrediente_id=ing.id,
            nombre=ing.nombre,
            cantidad=cantidad,
            unidad_medida=ing.unidad_medida,
            costo_unitario=ing.costo_unitario,
            subtotal=cantidad * ing.costo_unitario,
            stock_actual=ing.stock_cantidad if activo else Decimal("0"),
            es_producto_terminado=ing.es_producto_terminado,
            activo=activo,
        ))
    return insumos


def agregar_ingrediente(uow, producto_id: int, data: AsociarIngredienteRequest) -> ProductoIngredienteRead:
    """Asocia un insumo a un producto con cantidad y unidad; recalcula el precio
    (doc §5.2 POST /ingredientes)."""
    producto = uow.productos.get_by_id(producto_id)
    if not producto:
        _problem("PRODUCTO_NOT_FOUND", f"Producto {producto_id} no encontrado", status.HTTP_404_NOT_FOUND)

    ing = uow.ingredientes.get_by_id(data.ingrediente_id)
    if not ing:
        _problem("INSUMO_NOT_FOUND", f"Insumo {data.ingrediente_id} no encontrado", status.HTTP_404_NOT_FOUND)

    if any(l.ingrediente_id == data.ingrediente_id for l in uow.productos.get_ingrediente_links(producto_id)):
        _problem("INSUMO_DUPLICADO", f"El insumo {data.ingrediente_id} ya está asociado al producto", status.HTTP_409_CONFLICT)

    if data.unidad_medida_id is not None and not uow.unidades.get_by_id(data.unidad_medida_id):
        _problem("UNIDAD_NOT_FOUND", f"Unidad de medida {data.unidad_medida_id} no encontrada", status.HTTP_404_NOT_FOUND)
    unidad_id = data.unidad_medida_id or _resolver_unidad_id(uow, ing.unidad_medida)

    uow.productos.add_ingrediente_link(
        producto_id=producto_id,
        ingrediente_id=ing.id,
        cantidad=float(data.cantidad),
        unidad_medida_id=unidad_id,
        es_removible=data.es_removible,
    )

    # Recalcular el precio con el insumo nuevo incluido.
    links = uow.productos.get_ingrediente_links(producto_id)
    cantidades = {l.ingrediente_id: Decimal(str(l.cantidad)) for l in links}
    insumos_orm = [uow.ingredientes.get_by_id(iid) for iid in cantidades]
    producto.precio_base = _calcular_precio(insumos_orm, cantidades, producto.margen_ganancia)
    producto.updated_at = datetime.utcnow()
    uow.productos.add(producto)

    return ProductoIngredienteRead(
        producto_id=producto_id,
        ingrediente_id=ing.id,
        nombre=ing.nombre,
        cantidad=Decimal(str(data.cantidad)),
        unidad_medida_id=unidad_id,
        es_removible=data.es_removible,
    )


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
