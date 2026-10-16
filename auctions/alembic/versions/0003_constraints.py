from alembic import op

revision = "0003_constraints"
down_revision = "0002_indexes"
branch_labels = None
depends_on = None


def upgrade():
    op.create_check_constraint("ck_auctions_dates", "auctions", "end_at > start_at")
    op.create_check_constraint(
        "ck_lots_starting_price_positive", "lots", "starting_price > 0"
    )
    op.create_check_constraint("ck_bids_amount_positive", "bids", "amount > 0")
    op.create_check_constraint("ck_sales_price_positive", "sales", "price > 0")


def downgrade():
    op.drop_constraint("ck_sales_price_positive", "sales", type_="check")
    op.drop_constraint("ck_bids_amount_positive", "bids", type_="check")
    op.drop_constraint("ck_lots_starting_price_positive", "lots", type_="check")
    op.drop_constraint("ck_auctions_dates", "auctions", type_="check")
