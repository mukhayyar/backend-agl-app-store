"""Add tags column to apps and app_submissions

Revision ID: 008_tags
Revises: 007_scan_blocked
Create Date: 2026-04-11
"""
from alembic import op
import sqlalchemy as sa

revision = '008_tags'
down_revision = '007'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('apps', sa.Column('tags', sa.JSON(), nullable=True))
    op.add_column('app_submissions', sa.Column('tags', sa.JSON(), nullable=True))

def downgrade():
    op.drop_column('apps', 'tags')
    op.drop_column('app_submissions', 'tags')
