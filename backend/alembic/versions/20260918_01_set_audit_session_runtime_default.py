"""Use runtime as the only audit session runtime stack.

Revision ID: 20260918_01
Revises: 20260711_01
"""

from alembic import op
import sqlalchemy as sa

revision = "20260918_01"
down_revision = "20260711_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE audit_sessions SET runtime_stack = 'runtime' WHERE runtime_stack IS NULL OR runtime_stack <> 'runtime'")
    op.alter_column(
        "audit_sessions",
        "runtime_stack",
        existing_type=sa.String(length=32),
        nullable=False,
        server_default="runtime",
    )


def downgrade() -> None:
    op.alter_column(
        "audit_sessions",
        "runtime_stack",
        existing_type=sa.String(length=32),
        nullable=False,
        server_default=None,
    )
