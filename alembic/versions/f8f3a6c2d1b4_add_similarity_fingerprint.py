"""add similarity fingerprint

Revision ID: f8f3a6c2d1b4
Revises: 8cd951190b78
Create Date: 2026-04-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f8f3a6c2d1b4"
down_revision: Union[str, Sequence[str], None] = "8cd951190b78"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("knowledge_documents", schema=None) as batch_op:
        batch_op.add_column(sa.Column("similarity_fingerprint", sa.String(length=64), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("knowledge_documents", schema=None) as batch_op:
        batch_op.drop_column("similarity_fingerprint")
