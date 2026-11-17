"""drop_chain_users_totp

Revision ID: c3f1a9d27e54
Revises: 27d034ace1bf
Create Date: 2026-11-17 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c3f1a9d27e54"
down_revision = "27d034ace1bf"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("chain_users", "totp")


def downgrade() -> None:
    op.add_column("chain_users", sa.Column("totp", sa.String(), nullable=True))
