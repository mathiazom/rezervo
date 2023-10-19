"""slack class notification receipts

Revision ID: 32ee2ebb79d2
Revises: a82b4e463f7d
Create Date: 2023-10-19 13:44:44.569137

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "32ee2ebb79d2"
down_revision = "a82b4e463f7d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "slack_class_notification_receipts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("slack_user_id", sa.String(), nullable=False),
        sa.Column(
            "integration",
            postgresql.ENUM(name="integration", create_type=False),
            nullable=False,
        ),
        sa.Column("class_id", sa.String(), nullable=False),
        sa.Column("channel_id", sa.String(), nullable=False),
        sa.Column("message_id", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_slack_class_notification_receipts_id"),
        "slack_class_notification_receipts",
        ["id"],
        unique=False,
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(
        op.f("ix_slack_class_notification_receipts_id"),
        table_name="slack_class_notification_receipts",
    )
    op.drop_table("slack_class_notification_receipts")
    # ### end Alembic commands ###
