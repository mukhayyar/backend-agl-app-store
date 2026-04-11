"""Add scan_blocked flag to apps

Revision ID: 007
Revises: 006
Create Date: 2026-04-11
"""
from alembic import op
import sqlalchemy as sa

revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('apps', sa.Column('scan_blocked', sa.Boolean(), nullable=True, server_default='false'))

def downgrade():
    op.drop_column('apps', 'scan_blocked')
