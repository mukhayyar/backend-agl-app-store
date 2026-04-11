"""Add email/password auth and organization email detection

Revision ID: 005
Revises: 004
Create Date: 2026-04-11
"""
from alembic import op
import sqlalchemy as sa

revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('users', sa.Column('email', sa.String(255), nullable=True, unique=False))
    op.add_column('users', sa.Column('password_hash', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('email_verified', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('users', sa.Column('email_verification_token', sa.String(128), nullable=True))
    op.add_column('users', sa.Column('email_verification_expires', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('password_reset_token', sa.String(128), nullable=True))
    op.add_column('users', sa.Column('password_reset_expires', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('is_organization_email', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('users', sa.Column('organization_domain', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('auth_provider', sa.String(20), nullable=False, server_default='github'))

def downgrade():
    for col in ['email','password_hash','email_verified','email_verification_token',
                'email_verification_expires','password_reset_token','password_reset_expires',
                'is_organization_email','organization_domain','auth_provider']:
        op.drop_column('users', col)
