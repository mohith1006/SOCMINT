"""add platform_post_id to posts for ingestion idempotency

Revision ID: 7a2f9c41e8b3
Revises: 1444182ae9e7
Create Date: 2026-09-13

Without this, re-running a live ingestion connector (Telegram/Reddit)
over any overlapping time window inserts full duplicate Post rows for
messages already ingested — every downstream count (trends, sentiment
timeline, network edge weights, demographic aggregates) silently
inflates a little more on every re-run. Nullable + unique together:
existing rows (synthetic data, anything ingested before this column
existed) keep platform_post_id=NULL and are unaffected, since Postgres
treats each NULL as distinct under a UNIQUE constraint.
"""
from alembic import op
import sqlalchemy as sa


revision = '7a2f9c41e8b3'
down_revision = '1444182ae9e7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('posts', sa.Column('platform_post_id', sa.String(), nullable=True))
    op.create_index('ix_posts_platform_post_id', 'posts', ['platform_post_id'])
    op.create_unique_constraint('uq_posts_platform_post_id', 'posts', ['platform', 'platform_post_id'])


def downgrade() -> None:
    op.drop_constraint('uq_posts_platform_post_id', 'posts', type_='unique')
    op.drop_index('ix_posts_platform_post_id', table_name='posts')
    op.drop_column('posts', 'platform_post_id')
