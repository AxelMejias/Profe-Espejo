-- Ejecutar este script en pgAdmin (Query Tool) sobre la DB parcial1_db
-- antes de reiniciar el backend con los nuevos modelos.

-- Relación reflexiva: columna padre en categoria
ALTER TABLE categoria ADD COLUMN IF NOT EXISTS parent_id INTEGER REFERENCES categoria(id);

-- Auditoría en categoria
ALTER TABLE categoria ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW() NOT NULL;
ALTER TABLE categoria ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP;

-- Auditoría en ingrediente
ALTER TABLE ingrediente ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW() NOT NULL;
ALTER TABLE ingrediente ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP;

-- Auditoría en producto
ALTER TABLE producto ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW() NOT NULL;
ALTER TABLE producto ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP;
