"""session class data

Revision ID: 250923213823
Revises: 6ce50e1900f7
Create Date: 2023-06-10 12:13:20.759383

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '250923213823'
down_revision = '6ce50e1900f7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('sessions', sa.Column('class_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('sessions', 'class_data')
    # ### end Alembic commands ###