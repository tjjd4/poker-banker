"""initial_schema

Revision ID: 2e9b7ac11bd5
Revises:
Create Date: 2026-03-03 23:27:17.587827

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON


# revision identifiers, used by Alembic.
revision: str = '2e9b7ac11bd5'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # --- users ---
    op.create_table(
        'users',
        sa.Column('id', UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('username', sa.String(50), unique=True, nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('display_name', sa.String(100), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )

    # --- jackpot_pools --- (must be before tables due to FK)
    op.create_table(
        'jackpot_pools',
        sa.Column('id', UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('balance', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('banker_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )

    # --- tables ---
    op.create_table(
        'tables',
        sa.Column('id', UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('blind_level', sa.String(20), nullable=False),
        sa.Column('rake_interval_minutes', sa.Integer(), nullable=False),
        sa.Column('rake_amount', sa.Integer(), nullable=False),
        sa.Column('jackpot_per_hand', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('jackpot_pool_id', UUID(as_uuid=True), sa.ForeignKey('jackpot_pools.id'), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='CREATED'),
        sa.Column('banker_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('opened_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )

    # --- player_seats ---
    op.create_table(
        'player_seats',
        sa.Column('id', UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('table_id', UUID(as_uuid=True), sa.ForeignKey('tables.id'), nullable=False),
        sa.Column('player_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('seated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('left_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.UniqueConstraint('table_id', 'player_id'),
    )

    # --- transactions ---
    op.create_table(
        'transactions',
        sa.Column('id', UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('table_id', UUID(as_uuid=True), sa.ForeignKey('tables.id'), nullable=False),
        sa.Column('player_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('type', sa.String(30), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('balance_after', sa.Integer(), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    op.create_index(
        'ix_transactions_table_player_created',
        'transactions',
        ['table_id', 'player_id', 'created_at'],
    )

    # --- insurance_events ---
    op.create_table(
        'insurance_events',
        sa.Column('id', UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('table_id', UUID(as_uuid=True), sa.ForeignKey('tables.id'), nullable=False),
        sa.Column('buyer_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('seller_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('buyer_hand', JSON(), nullable=False),
        sa.Column('opponent_hand', JSON(), nullable=False),
        sa.Column('community_cards', JSON(), nullable=False),
        sa.Column('outs', sa.Integer(), nullable=False),
        sa.Column('win_probability', sa.Float(), nullable=False),
        sa.Column('odds', sa.Float(), nullable=False),
        sa.Column('insured_amount', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('payout_amount', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('is_hit', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )

    # --- jackpot_triggers ---
    op.create_table(
        'jackpot_triggers',
        sa.Column('id', UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('pool_id', UUID(as_uuid=True), sa.ForeignKey('jackpot_pools.id'), nullable=False),
        sa.Column('table_id', UUID(as_uuid=True), sa.ForeignKey('tables.id'), nullable=False),
        sa.Column('winner_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('hand_description', sa.String(200), nullable=False),
        sa.Column('payout_amount', sa.Integer(), nullable=False),
        sa.Column('pool_balance_after', sa.Integer(), nullable=False),
        sa.Column('triggered_by', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('jackpot_triggers')
    op.drop_table('insurance_events')
    op.drop_index('ix_transactions_table_player_created', table_name='transactions')
    op.drop_table('transactions')
    op.drop_table('player_seats')
    op.drop_table('tables')
    op.drop_table('jackpot_pools')
    op.drop_table('users')
