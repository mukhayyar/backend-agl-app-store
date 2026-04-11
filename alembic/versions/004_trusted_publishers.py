"""Add trusted publisher system and developer GPG keys

Revision ID: 004
Revises: 003
Create Date: 2026-04-11
"""
from alembic import op
import sqlalchemy as sa

revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None

def upgrade():
    # Add trust fields to users
    op.add_column('users', sa.Column('is_trusted_publisher', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('users', sa.Column('trusted_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('trusted_by', sa.Integer(), nullable=True))

    # Developer personal GPG key table
    op.create_table(
        'developer_gpg_keys',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('fingerprint', sa.String(64), nullable=True),
        sa.Column('public_key', sa.Text(), nullable=True),
        sa.Column('uid', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
    )

    # Add is_verified to apps (true if published + trusted publisher + valid GPG)
    op.add_column('apps', sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='false'))

def downgrade():
    op.drop_column('users', 'is_trusted_publisher')
    op.drop_column('users', 'trusted_at')
    op.drop_column('users', 'trusted_by')
    op.drop_table('developer_gpg_keys')
    op.drop_column('apps', 'is_verified')
