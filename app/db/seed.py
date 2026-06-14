from decimal import Decimal
from sqlmodel import Session, select
from app.core.database import engine
from app.core.security import hash_password

from app.modules.auth.model import Rol, Usuario, UsuarioRol
from app.modules.pedidos.model import EstadoPedido, FormaPago
from app.modules.unidades.model import UnidadMedida
from app.modules.direcciones.model import DireccionEntrega  # noqa: F401 — registra el mapper
from app.modules.categorias.model import Categoria
from app.modules.ingredientes.model import Ingrediente
from app.modules.productos.model import Producto
from app.core.links import ProductoCategoria, ProductoIngrediente


def seed():
    with Session(engine) as session:
        _seed_roles(session)
        _seed_estados_pedido(session)
        _seed_formas_pago(session)
        _seed_unidades(session)
        _seed_admin(session)
        _seed_cocina(session)
        _seed_stock(session)
        _seed_catalogo_demo(session)
        print("Seed completado.")


def _seed_unidades(session: Session):
    unidades = [
        UnidadMedida(nombre="kilogramo", simbolo="kg",        tipo="peso"),
        UnidadMedida(nombre="gramo",     simbolo="g",         tipo="peso"),
        UnidadMedida(nombre="litro",     simbolo="L",         tipo="volumen"),
        UnidadMedida(nombre="mililitro", simbolo="ml",        tipo="volumen"),
        UnidadMedida(nombre="unidad",    simbolo="ud",        tipo="contable"),
        UnidadMedida(nombre="porción",   simbolo="porciones", tipo="contable"),
    ]
    for u in unidades:
        if not session.exec(select(UnidadMedida).where(UnidadMedida.nombre == u.nombre)).first():
            session.add(u)
    session.commit()


def _seed_roles(session: Session):
    roles = [
        Rol(codigo="ADMIN",   nombre="Administrador",      descripcion="Acceso total al sistema"),
        Rol(codigo="STOCK",   nombre="Gestor de Stock",    descripcion="Gestión de inventario"),
        Rol(codigo="PEDIDOS",  nombre="Gestor de Pedidos",  descripcion="Ver y avanzar estados de pedidos"),
        Rol(codigo="CLIENT",  nombre="Cliente",            descripcion="Cliente de la tienda"),
    ]
    for rol in roles:
        if not session.exec(select(Rol).where(Rol.codigo == rol.codigo)).first():
            session.add(rol)
    session.commit()


def _seed_estados_pedido(session: Session):
    # FSM v7 — exactamente 5 estados (se elimina EN_CAMINO de v5; sin ESPERANDO_PAGO).
    estados = [
        EstadoPedido(codigo="PENDIENTE",  descripcion="Pendiente de confirmación", orden=1, es_terminal=False),
        EstadoPedido(codigo="CONFIRMADO", descripcion="Confirmado",                orden=2, es_terminal=False),
        EstadoPedido(codigo="EN_PREP",    descripcion="En preparación",            orden=3, es_terminal=False),
        EstadoPedido(codigo="ENTREGADO",  descripcion="Entregado",                 orden=4, es_terminal=True),
        EstadoPedido(codigo="CANCELADO",  descripcion="Cancelado",                 orden=5, es_terminal=True),
    ]
    for estado in estados:
        if not session.exec(select(EstadoPedido).where(EstadoPedido.codigo == estado.codigo)).first():
            session.add(estado)
    session.commit()


def _seed_formas_pago(session: Session):
    # MercadoPago Checkout API operativo (módulo pagos + webhook IPN).
    formas = [
        FormaPago(codigo="EFECTIVO",     descripcion="Efectivo",                  habilitado=True),
        FormaPago(codigo="TRANSFERENCIA", descripcion="Transferencia bancaria",     habilitado=True),
        FormaPago(codigo="MERCADOPAGO",  descripcion="MercadoPago",                habilitado=True),
    ]
    for forma in formas:
        if not session.exec(select(FormaPago).where(FormaPago.codigo == forma.codigo)).first():
            session.add(forma)
    session.commit()


def _seed_admin(session: Session):
    if session.exec(select(Usuario).where(Usuario.email == "admin@foodstore.com")).first():
        return
    admin = Usuario(
        nombre="Admin",
        apellido="FoodStore",
        email="admin@foodstore.com",
        password_hash=hash_password("Admin1234!"),
    )
    session.add(admin)
    session.flush()
    session.add(UsuarioRol(usuario_id=admin.id, rol_codigo="ADMIN"))
    session.commit()


def _seed_cocina(session: Session):
    if session.exec(select(Usuario).where(Usuario.email == "cocina@foodstore.com")).first():
        return
    cocina = Usuario(
        nombre="Carlos",
        apellido="Cocina",
        email="cocina@foodstore.com",
        password_hash=hash_password("Cocina1234!"),
    )
    session.add(cocina)
    session.flush()
    session.add(UsuarioRol(usuario_id=cocina.id, rol_codigo="PEDIDOS"))
    session.commit()


def _seed_stock(session: Session):
    if session.exec(select(Usuario).where(Usuario.email == "stock@foodstore.com")).first():
        return
    stock = Usuario(
        nombre="Laura",
        apellido="Stock",
        email="stock@foodstore.com",
        password_hash=hash_password("Stock1234!"),
    )
    session.add(stock)
    session.flush()
    session.add(UsuarioRol(usuario_id=stock.id, rol_codigo="STOCK"))
    session.commit()


def _seed_catalogo_demo(session: Session):
    """
    Catálogo de ejemplo para que la tienda no quede vacía en una DB nueva.
    Idempotente: si ya hay algún producto, no hace nada.
    El stock es por INSUMO; los productos descuentan stock de sus ingredientes.
    """
    if session.exec(select(Producto)).first():
        return  # ya hay productos cargados

    # ── Categorías ────────────────────────────────────────────────────────────
    cats: dict[str, Categoria] = {}
    for nombre, desc in [
        ("Hamburguesas", "Nuestras burgers a la parrilla"),
        ("Pizzas",       "Pizzas a la piedra"),
        ("Bebidas",      "Bebidas frías"),
        ("Postres",      "Para cerrar la comida"),
    ]:
        c = Categoria(nombre=nombre, descripcion=desc)
        session.add(c)
        cats[nombre] = c
    session.flush()

    # ── Insumos (Ingredientes con stock) ──────────────────────────────────────
    # nombre, unidad_medida, costo_unitario, stock, es_alergeno, es_producto_terminado
    insumo_defs = [
        ("Pan de hamburguesa", "unidad", "80",   "1000", True,  False),
        ("Medallón de carne",  "unidad", "250",  "1000", False, False),
        ("Queso cheddar",      "feta",   "60",   "1000", True,  False),
        ("Lechuga",            "gramo",  "2",     "5000", False, False),
        ("Tomate",             "gramo",  "1.5",   "5000", False, False),
        ("Masa de pizza",      "unidad", "150",   "500",  True,  False),
        ("Salsa de tomate",    "ml",     "0.5",  "10000", False, False),
        ("Mozzarella",         "gramo",  "4",     "8000", True,  False),
        ("Gaseosa lata 354ml", "unidad", "300",   "500",  False, True),
        ("Helado (pote)",      "gramo",  "5",     "4000", True,  False),
    ]
    insumos: dict[str, Ingrediente] = {}
    for nombre, unidad, costo, stock, alergeno, terminado in insumo_defs:
        ing = Ingrediente(
            nombre=nombre,
            unidad_medida=unidad,
            costo_unitario=Decimal(costo),
            stock_cantidad=Decimal(stock),
            stock_minimo=Decimal("10"),
            es_alergeno=alergeno,
            es_producto_terminado=terminado,
        )
        session.add(ing)
        insumos[nombre] = ing
    session.flush()

    ud = session.exec(select(UnidadMedida).where(UnidadMedida.simbolo == "ud")).first()
    unidad_venta_id = ud.id if ud else None
    margen = Decimal("0.30")
    _REMOVIBLES = {"Lechuga", "Tomate", "Queso cheddar"}

    def crear_producto(nombre, descripcion, categoria, imagen, receta):
        """receta: lista de (nombre_insumo, cantidad)."""
        costo = sum(insumos[n].costo_unitario * Decimal(str(c)) for n, c in receta)
        precio = (costo * (Decimal("1") + margen)).quantize(Decimal("0.01"))
        p = Producto(
            nombre=nombre,
            descripcion=descripcion,
            imagenes_url=[imagen],
            precio=precio,
            margen_ganancia=margen,
            disponible=True,
            unidad_venta_id=unidad_venta_id,
        )
        session.add(p)
        session.flush()
        session.add(ProductoCategoria(producto_id=p.id, categoria_id=categoria.id, es_principal=True))
        for n, c in receta:
            session.add(ProductoIngrediente(
                producto_id=p.id,
                ingrediente_id=insumos[n].id,
                cantidad=Decimal(str(c)),
                es_removible=(n in _REMOVIBLES),
            ))

    crear_producto(
        "Hamburguesa Clásica", "Carne, cheddar, lechuga y tomate en pan artesanal.",
        cats["Hamburguesas"], "https://placehold.co/600x400?text=Hamburguesa+Clasica",
        [("Pan de hamburguesa", 1), ("Medallón de carne", 1), ("Queso cheddar", 1),
         ("Lechuga", 20), ("Tomate", 30)],
    )
    crear_producto(
        "Doble Cheese", "Doble medallón de carne y doble cheddar.",
        cats["Hamburguesas"], "https://placehold.co/600x400?text=Doble+Cheese",
        [("Pan de hamburguesa", 1), ("Medallón de carne", 2), ("Queso cheddar", 2)],
    )
    crear_producto(
        "Pizza Muzzarella", "Mozzarella y salsa de tomate a la piedra.",
        cats["Pizzas"], "https://placehold.co/600x400?text=Pizza+Muzzarella",
        [("Masa de pizza", 1), ("Salsa de tomate", 150), ("Mozzarella", 250)],
    )
    crear_producto(
        "Gaseosa en lata", "Bebida fría 354 ml.",
        cats["Bebidas"], "https://placehold.co/600x400?text=Gaseosa",
        [("Gaseosa lata 354ml", 1)],
    )
    crear_producto(
        "Helado 1/4 kg", "Helado artesanal, sabores a elección.",
        cats["Postres"], "https://placehold.co/600x400?text=Helado",
        [("Helado (pote)", 250)],
    )

    session.commit()
    print("Seed de catálogo demo completado (5 productos).")


if __name__ == "__main__":
    seed()