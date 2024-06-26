"""rename_auth_token_to_auth_data

Revision ID: 4d51198ec426
Revises: 52c8a741cd0e
Create Date: 2024-03-31 15:53:48.869834

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "4d51198ec426"
down_revision = "52c8a741cd0e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column("chain_users", "auth_token", new_column_name="auth_data")
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column("chain_users", "auth_data", new_column_name="auth_token")
    # ### end Alembic commands ###
