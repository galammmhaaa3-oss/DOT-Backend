"""Add driver identity verification fields

Revision ID: 001
Revises: 
Create Date: 2026-02-02 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add identity verification fields to users table
    op.add_column('users', sa.Column('id_name', sa.String(), nullable=True))
    op.add_column('users', sa.Column('national_id', sa.String(), nullable=True))
    op.add_column('users', sa.Column('id_photo_url', sa.String(), nullable=True))
    op.add_column('users', sa.Column('birth_date', sa.DateTime(timezone=True), nullable=True))
    
    # Add unique constraint for national_id
    op.create_unique_constraint('uq_users_national_id', 'users', ['national_id'])


def downgrade() -> None:
    # Remove unique constraint
    op.drop_constraint('uq_users_national_id', 'users', type_='unique')
    
    # Remove columns
    op.drop_column('users', 'birth_date')
    op.drop_column('users', 'id_photo_url')
    op.drop_column('users', 'national_id')
    op.drop_column('users', 'id_name')
