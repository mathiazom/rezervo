"""required unique user names

Revision ID: f30ee2562e70
Revises: 250923213823
Create Date: 2023-08-23 11:30:43.016254

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "f30ee2562e70"
down_revision = "250923213823"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column("users", "name", existing_type=sa.VARCHAR(), nullable=False)
    op.create_unique_constraint(None, "users", ["name"])
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, "users", type_="unique")
    op.alter_column("users", "name", existing_type=sa.VARCHAR(), nullable=True)
    # ### end Alembic commands ###