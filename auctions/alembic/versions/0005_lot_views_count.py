"""Lab 3: счётчик просмотров лота (новая функция, требующая изменения схемы).

Колонка добавляется как NOT NULL с server_default '0', поэтому миграция
безопасно применяется и к пустой БД, и к БД, где уже есть лоты: существующие
строки получают views_count = 0.
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_lot_views_count"
down_revision = "0004_users_and_sessions"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "lots",
        sa.Column("views_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_check_constraint(
        "ck_lots_views_count_non_negative", "lots", "views_count >= 0"
    )


def downgrade():
    op.drop_constraint("ck_lots_views_count_non_negative", "lots", type_="check")
    op.drop_column("lots", "views_count")
