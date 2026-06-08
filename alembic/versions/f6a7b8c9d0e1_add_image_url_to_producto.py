"""add_image_url_to_producto

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-06-07 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("producto", sa.Column("image_url", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("producto", "image_url")
