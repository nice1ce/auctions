from alembic import op

revision = "0002_indexes"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("ix_bids_lot_id", "bids", ["lot_id"])
    op.create_index("ix_bids_buyer_id", "bids", ["buyer_id"])
    op.create_index("ix_lots_auction_id", "lots", ["auction_id"])
    op.create_index("ix_lots_seller_id", "lots", ["seller_id"])


def downgrade():
    op.drop_index("ix_lots_seller_id", table_name="lots")
    op.drop_index("ix_lots_auction_id", table_name="lots")
    op.drop_index("ix_bids_buyer_id", table_name="bids")
    op.drop_index("ix_bids_lot_id", table_name="bids")
