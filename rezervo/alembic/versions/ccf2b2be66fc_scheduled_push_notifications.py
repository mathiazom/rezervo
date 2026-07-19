"""scheduled push notifications

Revision ID: ccf2b2be66fc
Revises: 27d034ace1bf
Create Date: 2026-07-06 22:26:06.383649

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "ccf2b2be66fc"
down_revision = "27d034ace1bf"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scheduled_push_notifications",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("message", sa.String(), nullable=False),
        sa.Column("send_at", sa.DateTime(), nullable=False),
        sa.Column("cancellation_key", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="cascade"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_scheduled_push_notifications_cancellation_key"),
        "scheduled_push_notifications",
        ["cancellation_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_scheduled_push_notifications_id"),
        "scheduled_push_notifications",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_scheduled_push_notifications_send_at"),
        "scheduled_push_notifications",
        ["send_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_scheduled_push_notifications_user_id"),
        "scheduled_push_notifications",
        ["user_id"],
        unique=False,
    )
    op.add_column(
        "push_notification_subscriptions",
        sa.Column(
            "grants",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text(
                '\'{"booking": false, "community": false, "reminder": false}\'::jsonb'
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column("push_notification_subscriptions", "grants")
    op.drop_index(
        op.f("ix_scheduled_push_notifications_user_id"),
        table_name="scheduled_push_notifications",
    )
    op.drop_index(
        op.f("ix_scheduled_push_notifications_send_at"),
        table_name="scheduled_push_notifications",
    )
    op.drop_index(
        op.f("ix_scheduled_push_notifications_id"),
        table_name="scheduled_push_notifications",
    )
    op.drop_index(
        op.f("ix_scheduled_push_notifications_cancellation_key"),
        table_name="scheduled_push_notifications",
    )
    op.drop_table("scheduled_push_notifications")
