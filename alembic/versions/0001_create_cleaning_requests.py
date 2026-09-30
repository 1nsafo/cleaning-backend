"""Create cleaning requests."""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "cleaning_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("phone", sa.String(12), nullable=False),
        sa.Column("cleaning_type", sa.String(32), nullable=False),
        sa.Column("contact_method", sa.String(16), nullable=False),
        sa.Column("name", sa.String(100)),
        sa.Column("comment", sa.String(2000)),
        sa.Column("privacy_consent", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(16), server_default="new", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("privacy_consent = true", name="ck_requests_consent"),
        sa.CheckConstraint("cleaning_type IN ('maintenance', 'general', 'after_renovation')", name="ck_requests_cleaning_type"),
        sa.CheckConstraint("contact_method IN ('call', 'message')", name="ck_requests_contact_method"),
    )
    op.create_index("ix_cleaning_requests_created_at", "cleaning_requests", ["created_at"])


def downgrade():
    op.drop_index("ix_cleaning_requests_created_at", table_name="cleaning_requests")
    op.drop_table("cleaning_requests")
