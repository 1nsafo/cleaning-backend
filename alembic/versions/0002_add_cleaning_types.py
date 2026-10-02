"""Add windows and not_sure cleaning types."""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("ck_requests_cleaning_type", "cleaning_requests", type_="check")
    op.create_check_constraint(
        "ck_requests_cleaning_type", "cleaning_requests",
        "cleaning_type IN ('maintenance', 'general', 'after_renovation', 'windows', 'not_sure')",
    )


def downgrade():
    # Откат упадёт, если в таблице уже есть заявки с новыми типами.
    op.drop_constraint("ck_requests_cleaning_type", "cleaning_requests", type_="check")
    op.create_check_constraint(
        "ck_requests_cleaning_type", "cleaning_requests",
        "cleaning_type IN ('maintenance', 'general', 'after_renovation')",
    )
