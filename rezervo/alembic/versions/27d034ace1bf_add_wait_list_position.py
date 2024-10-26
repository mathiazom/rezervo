"""add_wait_list_position

Revision ID: 27d034ace1bf
Revises: 6133793acba4
Create Date: 2024-05-13 22:15:21.451924

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "27d034ace1bf"
down_revision = "6133793acba4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "sessions", sa.Column("position_in_wait_list", sa.Integer(), nullable=True)
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("sessions", "position_in_wait_list")
    # ### end Alembic commands ###