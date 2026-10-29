"""Merge Agent collaboration and TikTok seller multishop migration histories."""

revision = "041_merge_agent_multishop_collab"
down_revision = ("040_agent_collaboration", "035_tiktok_seller_multishop")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
