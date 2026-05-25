-- ============================================================
-- SEED DATA — Food Store Integrador
-- Categorias, Ingredientes, Productos y sus relaciones
--
-- REQUISITOS: tener la DB creada y las migraciones aplicadas.
--   alembic upgrade head
--
-- COMO EJECUTAR (desde la raiz del proyecto):
--   Windows:
--     $env:PGPASSWORD = "tu_password"
--     & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d foodstore_db -f app/db/seed_data.sql
--
--   Mac/Linux:
--     PGPASSWORD=tu_password psql -U postgres -d foodstore_db -f app/db/seed_data.sql
--
-- NOTA: el seed.py que corre automatico al iniciar el servidor
-- ya se encarga de: roles, estados de pedido, formas de pago y usuario admin.
-- Este archivo agrega los datos de catalogo (productos, ingredientes, categorias).
-- ============================================================


-- CATEGORIAS (padres primero, luego hijos)
INSERT INTO categoria (id, nombre, descripcion, parent_id, created_at) VALUES
  (7, 'Comidas',      NULL,                           NULL, NOW()),
  (8, 'Bebidas',      NULL,                           NULL, NOW()),
  (1, 'Hamburguesas', NULL,                              7, NOW()),
  (2, 'Refrescos',    'Frios y calientes',               8, NOW()),
  (3, 'Postres',      'Dulces para cerrar',              8, NOW()),
  (4, 'Combos',       'Arma tu combo completo',          7, NOW()),
  (5, 'Jugos',        'Jugos Frescos y Naturales',       8, NOW()),
  (9, 'Empanadas',    NULL,                              7, NOW());

SELECT setval('categoria_id_seq', (SELECT MAX(id) FROM categoria));


-- INGREDIENTES
INSERT INTO ingrediente (id, nombre, descripcion, unidad_medida, es_alergeno, created_at) VALUES
  (1,  'Medallon de carne 150g',  'Medallon de carne vacuna, 150g.',                    'UNIDAD', false, NOW()),
  (2,  'Pan brioche',             'Pan artesanal con semillas de sesamo',               'UNIDAD', true,  NOW()),
  (3,  'Hoja de lechuga',         'Lechuga fresca',                                    'UNIDAD', false, NOW()),
  (4,  'Tomate',                  'Tomate fresco en rodajas',                          'UNIDAD', false, NOW()),
  (5,  'Queso cheddar',           'Feta de queso cheddar madurado, 25g',               'UNIDAD', true,  NOW()),
  (6,  'Aros de cebolla',         'Cebolla en aros',                                   'UNIDAD', false, NOW()),
  (7,  'Panceta',                 'Panceta ahumada crocante',                          'G',      false, NOW()),
  (8,  'Salsa BBQ',               'Salsa barbecue ahumada',                            'G',      false, NOW()),
  (9,  'Ketchup',                 'Salsa de tomate',                                   'G',      false, NOW()),
  (10, 'Mayonesa',                'Mayonesa casera',                                   'G',      true,  NOW()),
  (11, 'Chocolate',               'Cobertura de chocolate negro',                      'G',      true,  NOW()),
  (12, 'Harina de trigo',         'Harina',                                            'G',      true,  NOW()),
  (13, 'Huevo',                   'Huevo de gallina',                                  'UNIDAD', true,  NOW()),
  (14, 'Azucar',                  'Azucar refinada',                                   'G',      false, NOW()),
  (15, 'Helado de vainilla',      'Crema de vainilla artesanal',                       'G',      true,  NOW()),
  (16, 'Crema de leche',          'Crema para reposteria',                             'ML',     true,  NOW()),
  (17, 'Naranja',                 'Naranja fresca exprimida',                          'UNIDAD', false, NOW()),
  (18, 'Tapa de empanada',        'Base crocante para el relleno clasico de empanada.','UNIDAD', false, NOW()),
  (19, 'Carne Picada',            'Carne picada de vaca de calidad.',                  'G',      false, NOW()),
  (20, 'Cebolla',                 'Cebolla fresca rehogada. 30g.',                     'G',      false, NOW()),
  (21, 'Aceitunas',               'Aceitunas verdes picadas',                          'UNIDAD', false, NOW()),
  (22, 'Botella de Agua Mineral', 'Botella de Agua Mineral sin gas, 500ml',            'UNIDAD', false, NOW()),
  (23, 'Botella de Coca Cola',    'Botella de Coca Cola chica, 500ml',                 'UNIDAD', false, NOW());

SELECT setval('ingrediente_id_seq', (SELECT MAX(id) FROM ingrediente));


-- PRODUCTOS
INSERT INTO producto (id, nombre, descripcion, precio, stock_cantidad, disponible, created_at) VALUES
  (1,  'Hamburguesa Clasica',        'Medallon, cebolla, tomate y queso cheddar. Incluye papas fritas chicas.',                             8000.00, 45, true, NOW()),
  (2,  'Hamburguesa Doble Completa', 'Doble medallon con cebolla, panceta, huevo, tomate, lechuga y cheddar. Incluye papas fritas chicas.', 13000.00, 30, true, NOW()),
  (3,  'Hamburguesa BBQ',            'Medallon, panceta, cebolla, tomate y salsa BBQ. Incluye papas fritas chicas.',                        9000.00, 25, true, NOW()),
  (4,  'Coca-Cola',                  'Botella de Coca Cola, 500ml',                                                                         2500.00, 99, true, NOW()),
  (5,  'Agua Mineral',               'Sin gas, 500ml',                                                                                      2000.00, 78, true, NOW()),
  (6,  'Jugo de Naranja',            'Natural exprimido',                                                                                   3500.00, 40, true, NOW()),
  (7,  'Brownie con helado',         'Brownie tibio + bocha de vainilla',                                                                   5000.00, 19, true, NOW()),
  (8,  'Combo Clasico',              'Hamburguesa Clasica + bebida a eleccion. Incluye papas fritas chicas.',                               10000.00, 40, true, NOW()),
  (10, 'Empanada de Carne',          'Empanada de Carne Frita o al Horno. 1 unidad.',                                                       1100.00, 48, true, NOW());

SELECT setval('producto_id_seq', (SELECT MAX(id) FROM producto));


-- RELACIONES PRODUCTO <-> CATEGORIA
INSERT INTO producto_categoria (producto_id, categoria_id) VALUES
  (1,  1),   -- Hamburguesa Clasica        → Hamburguesas
  (2,  1),   -- Hamburguesa Doble Completa → Hamburguesas
  (3,  1),   -- Hamburguesa BBQ            → Hamburguesas
  (4,  2),   -- Coca-Cola                  → Refrescos
  (5,  2),   -- Agua Mineral               → Refrescos
  (6,  5),   -- Jugo de Naranja            → Jugos
  (7,  3),   -- Brownie con helado         → Postres
  (8,  4),   -- Combo Clasico              → Combos
  (10, 9);   -- Empanada de Carne          → Empanadas


-- RELACIONES PRODUCTO <-> INGREDIENTE (con cantidades reales)
INSERT INTO producto_ingrediente (producto_id, ingrediente_id, cantidad) VALUES
  -- Hamburguesa Clasica
  (1,  1,   1),   -- Medallon de carne 150g  x1
  (1,  2,   1),   -- Pan brioche             x1
  (1,  4,   2),   -- Tomate                  x2
  (1,  5,   1),   -- Queso cheddar           x1
  (1,  6,   2),   -- Aros de cebolla         x2
  (1,  9,  15),   -- Ketchup                 15g
  (1, 10,  15),   -- Mayonesa                15g

  -- Hamburguesa Doble Completa
  (2,  1,   2),   -- Medallon de carne 150g  x2
  (2,  2,   1),   -- Pan brioche             x1
  (2,  3,   1),   -- Hoja de lechuga         x1
  (2,  4,   2),   -- Tomate                  x2
  (2,  5,   2),   -- Queso cheddar           x2
  (2,  6,   3),   -- Aros de cebolla         x3
  (2,  7,  50),   -- Panceta                 50g
  (2,  9,  20),   -- Ketchup                 20g
  (2, 10,  20),   -- Mayonesa                20g
  (2, 13,   1),   -- Huevo                   x1

  -- Hamburguesa BBQ
  (3,  1,   1),   -- Medallon de carne 150g  x1
  (3,  2,   1),   -- Pan brioche             x1
  (3,  4,   2),   -- Tomate                  x2
  (3,  5,   1),   -- Queso cheddar           x1
  (3,  6,   2),   -- Aros de cebolla         x2
  (3,  7,  40),   -- Panceta                 40g
  (3,  8,  15),   -- Salsa BBQ               15g

  -- Coca-Cola
  (4, 23,   1),   -- Botella de Coca Cola    x1

  -- Agua Mineral
  (5, 22,   1),   -- Botella de Agua Mineral x1

  -- Jugo de Naranja
  (6, 17,   2),   -- Naranja                 x2

  -- Brownie con helado
  (7, 11,  90),   -- Chocolate               90g
  (7, 12,  50),   -- Harina de trigo         50g
  (7, 13,   2),   -- Huevo                   x2
  (7, 14,  60),   -- Azucar                  60g
  (7, 15, 130),   -- Helado de vainilla      130g
  (7, 16,  50),   -- Crema de leche          50ml

  -- Combo Clasico
  (8,  1,   1),   -- Medallon de carne 150g  x1
  (8,  2,   1),   -- Pan brioche             x1
  (8,  4,   1),   -- Tomate                  x1
  (8,  5,   1),   -- Queso cheddar           x1
  (8,  6,   2),   -- Aros de cebolla         x2
  (8,  9,  15),   -- Ketchup                 15g
  (8, 10,  15),   -- Mayonesa                15g

  -- Empanada de Carne
  (10, 13,   1),  -- Huevo                   x1
  (10, 18,   1),  -- Tapa de empanada        x1
  (10, 19,  70),  -- Carne Picada            70g
  (10, 20,   1),  -- Cebolla                 x1 (30g segun desc)
  (10, 21,   2);  -- Aceitunas               x2
