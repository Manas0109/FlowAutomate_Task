"""add attachment support

Revision ID: a1b2c3d4e5f6
Revises: 6355d91da57d
Create Date: 2026-04-05 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '6355d91da57d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema — add attachment support."""
    
    # Create enums idempotently (safe if type already exists)
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'upload_status') THEN
                CREATE TYPE upload_status AS ENUM ('pending', 'uploaded', 'failed');
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'message_type') THEN
                CREATE TYPE message_type AS ENUM ('text', 'attachment');
            END IF;
        END $$;
        """
    )

    upload_status_enum = postgresql.ENUM(
        'pending', 'uploaded', 'failed', name='upload_status', create_type=False
    )
    message_type_enum = postgresql.ENUM(
        'text', 'attachment', name='message_type', create_type=False
    )
    
    # Create attachments table
    op.create_table(
        'attachments',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('room_id', sa.String(), nullable=False),
        sa.Column('uploader_user_id', sa.String(), nullable=False),
        sa.Column('filename', sa.String(), nullable=False),
        sa.Column('content_type', sa.String(), nullable=False),
        sa.Column('size_bytes', sa.Integer(), nullable=False),
        sa.Column('storage_key', sa.String(), nullable=False),
        sa.Column(
            'upload_status',
            upload_status_enum,
            nullable=False,
            server_default='pending',
        ),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('storage_key', name='uq_attachment_storage_key'),
    )
    op.create_index(op.f('ix_attachments_room_id'), 'attachments', ['room_id'], unique=False)
    
    # Alter messages table: make text nullable, add message_type, add attachment_id
    op.alter_column('messages', 'text',
               existing_type=sa.Text(),
               nullable=True)
    op.add_column('messages', sa.Column(
        'message_type',
        message_type_enum,
        nullable=False,
        server_default='text',
    ))
    op.add_column('messages', sa.Column(
        'attachment_id',
        postgresql.UUID(as_uuid=True),
        nullable=True,
    ))
    op.create_unique_constraint('uq_message_attachment_id', 'messages', ['attachment_id'])
    op.create_foreign_key(
        'fk_message_attachment_id',
        'messages', 'attachments',
        ['attachment_id'], ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    """Downgrade schema — remove attachment support."""
    
    # Remove message table constraints and columns
    op.drop_constraint('fk_message_attachment_id', 'messages', type_='foreignkey')
    op.drop_constraint('uq_message_attachment_id', 'messages', type_='unique')
    op.drop_column('messages', 'attachment_id')
    op.drop_column('messages', 'message_type')
    
    # Make text non-nullable again
    op.alter_column('messages', 'text',
               existing_type=sa.Text(),
               nullable=False)
    
    # Drop attachments table
    op.drop_index(op.f('ix_attachments_room_id'), table_name='attachments')
    op.drop_table('attachments')
    
    # Drop enums
    postgresql.ENUM('pending', 'uploaded', 'failed', name='upload_status').drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM('text', 'attachment', name='message_type').drop(op.get_bind(), checkfirst=True)
