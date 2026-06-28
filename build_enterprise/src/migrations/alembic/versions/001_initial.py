# src/migrations/alembic/versions/001_initial_schema.py
"""Initial CrownStar schema

Revision ID: 001_initial
Revises: 
Create Date: 2026-06-13 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('conversations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('user_id', sa.String(255), nullable=False),
        sa.Column('user_message', sa.Text(), nullable=False),
        sa.Column('assistant_message', sa.Text(), nullable=False),
        sa.Column('modules_active', sa.Text(), nullable=True),
        sa.Column('language_model', sa.String(255), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('tenant_id', sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_conversations_user', 'conversations', ['user_id'])
    op.create_index('idx_conversations_timestamp', 'conversations', ['timestamp'])
    op.create_table('users',
        sa.Column('user_id', sa.String(255), nullable=False),
        sa.Column('username', sa.String(255), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('tier', sa.String(50), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('user_id'),
        sa.UniqueConstraint('email')
    )

def downgrade():
    op.drop_table('conversations')
    op.drop_table('users')
