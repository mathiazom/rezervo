"""integration_user_integration_to_chain

Revision ID: 361dceb969cb
Revises: fa1d494eb00d
Create Date: 2023-12-23 23:50:14.197969

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "361dceb969cb"
down_revision = "fa1d494eb00d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column(
        "integration_users",
        "integration",
        new_column_name="chain",
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column(
        "integration_users",
        "chain",
        new_column_name="integration",
    )
    # ### end Alembic commands ###
