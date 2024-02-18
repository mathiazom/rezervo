"""add_expires_at_to_slack_class_notification_receipt

Revision ID: eeac56f2034e
Revises: a95d01b29b2a
Create Date: 2023-12-31 14:37:05.189218

"""

import contextlib
import datetime
import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy import Column, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base

# revision identifiers, used by Alembic.
revision = "eeac56f2034e"
down_revision = "a95d01b29b2a"
branch_labels = None
depends_on = None


Base = declarative_base()


class SlackClassNotificationReceipt(Base):
    __tablename__ = "slack_class_notification_receipts"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    slack_user_id = Column(String, nullable=False)
    chain = Column(String, nullable=False)
    class_id = Column(String, nullable=False)
    channel_id = Column(String, nullable=False)
    message_id = Column(String, nullable=False)
    scheduled_reminder_id = Column(String, nullable=True)
    expires_at = Column(DateTime, nullable=False)


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "slack_class_notification_receipts",
        sa.Column("expires_at", sa.DateTime(), nullable=True),
    )
    session = sa.orm.Session(bind=op.get_bind())
    for receipt in session.query(SlackClassNotificationReceipt):
        message_sent_at = datetime.datetime.now()  # fallback
        message_id = receipt.message_id
        if message_id is not None:
            with contextlib.suppress(Exception):
                # attempt to extract the timestamp from the message_id
                message_sent_at = datetime.datetime.fromtimestamp(float(message_id))
        receipt.expires_at = message_sent_at + datetime.timedelta(days=30)
    session.commit()
    op.alter_column("slack_class_notification_receipts", "expires_at", nullable=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("slack_class_notification_receipts", "expires_at")
    # ### end Alembic commands ###
