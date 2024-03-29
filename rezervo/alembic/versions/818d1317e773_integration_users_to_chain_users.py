"""integration_users_to_chain_users

Revision ID: 818d1317e773
Revises: 8823a3ebec51
Create Date: 2023-12-24 00:00:06.262994

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "818d1317e773"
down_revision = "8823a3ebec51"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.rename_table("integration_users", "chain_users")
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.rename_table("chain_users", "integration_users")
    # ### end Alembic commands ###
