"""Add flatpak scan result columns to apps

Revision ID: 006
Revises: 005
Create Date: 2026-04-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('apps', sa.Column('scan_result', JSONB, nullable=True))
    op.add_column('apps', sa.Column('scan_verdict', sa.String(16), nullable=True))
    op.add_column('apps', sa.Column('scan_at', sa.DateTime(), nullable=True))

def downgrade():
    op.drop_column('apps', 'scan_at')
    op.drop_column('apps', 'scan_verdict')
    op.drop_column('apps', 'scan_result')
