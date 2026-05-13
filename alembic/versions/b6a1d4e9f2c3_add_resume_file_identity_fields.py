"""add resume file identity fields

Revision ID: b6a1d4e9f2c3
Revises: 9f04e319acd4
Create Date: 2026-05-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b6a1d4e9f2c3"
down_revision: Union[str, Sequence[str], None] = "9f04e319acd4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("resume_records", schema=None) as batch_op:
        batch_op.add_column(sa.Column("resume_id", sa.String(length=64), nullable=True))
        batch_op.add_column(
            sa.Column("file_path", sa.String(length=500), nullable=False, server_default="")
        )
        batch_op.add_column(
            sa.Column("file_ext", sa.String(length=20), nullable=False, server_default="")
        )

    op.execute("UPDATE resume_records SET resume_id = CAST(id AS TEXT) WHERE resume_id IS NULL")

    with op.batch_alter_table("resume_records", schema=None) as batch_op:
        batch_op.alter_column("resume_id", existing_type=sa.String(length=64), nullable=False)
        batch_op.create_index(batch_op.f("ix_resume_records_resume_id"), ["resume_id"], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("resume_records", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_resume_records_resume_id"))
        batch_op.drop_column("file_ext")
        batch_op.drop_column("file_path")
        batch_op.drop_column("resume_id")
