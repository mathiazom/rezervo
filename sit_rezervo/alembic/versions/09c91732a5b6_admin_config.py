"""admin config

Revision ID: 09c91732a5b6
Revises: 141159a3cb17
Create Date: 2023-03-26 16:31:04.422940

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '09c91732a5b6'
down_revision = '141159a3cb17'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('configs', sa.Column('admin_config', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('configs', 'admin_config')
    # ### end Alembic commands ###