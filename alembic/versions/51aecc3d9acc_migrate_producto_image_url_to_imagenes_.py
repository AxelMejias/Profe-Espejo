"""migrate_producto_image_url_to_imagenes_url_array

Revision ID: 51aecc3d9acc
Revises: bf64eab07060
Create Date: 2026-06-13 17:30:35.029284

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = '51aecc3d9acc'
down_revision: Union[str, None] = 'bf64eab07060'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('producto', sa.Column('imagenes_url', sa.ARRAY(sa.Text()), nullable=True))
    op.execute("""
        UPDATE producto
        SET imagenes_url = ARRAY[image_url]
        WHERE image_url IS NOT NULL
    """)
    op.execute("""
        UPDATE producto
        SET imagenes_url = '{}'
        WHERE imagenes_url IS NULL
    """)
    op.alter_column('producto', 'imagenes_url', nullable=False, server_default='{}')
    op.drop_column('producto', 'image_url')


def downgrade() -> None:
    op.add_column('producto', sa.Column('image_url', sa.Text(), nullable=True))
    op.execute("""
        UPDATE producto
        SET image_url = imagenes_url[1]
        WHERE array_length(imagenes_url, 1) > 0
    """)
    op.drop_column('producto', 'imagenes_url')
