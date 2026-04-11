"""Add GPG keys and expiry to apps table

Revision ID: 003
Revises: 002
Create Date: 2026-04-11
"""
from alembic import op
import sqlalchemy as sa

revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('apps', sa.Column('published', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('apps', sa.Column('expires_at', sa.DateTime(), nullable=True))
    op.add_column('apps', sa.Column('gpg_fingerprint', sa.String(64), nullable=True))
    op.add_column('apps', sa.Column('gpg_public_key', sa.Text(), nullable=True))
    op.add_column('apps', sa.Column('gpg_uid', sa.String(255), nullable=True))
    op.add_column('apps', sa.Column('owner_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('apps', sa.Column('reminder_30_sent', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('apps', sa.Column('reminder_7_sent', sa.Boolean(), nullable=False, server_default='false'))

def downgrade():
    for col in ['published', 'expires_at', 'gpg_fingerprint', 'gpg_public_key', 'gpg_uid', 'owner_user_id', 'reminder_30_sent', 'reminder_7_sent']:
        op.drop_column('apps', col)
