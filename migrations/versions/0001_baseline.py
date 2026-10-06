"""Baseline: schema as it was before migrations were introduced.

Databases created earlier by Base.metadata.create_all() are stamped with this
revision by app.db.base.init_db() instead of running it.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-10-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('settings',
    sa.Column('key', sa.String(length=100), nullable=False),
    sa.Column('value', sa.JSON(), nullable=False),
    sa.Column('description', sa.String(length=255), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('key')
    )
    op.create_table('users',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('telegram_id', sa.BigInteger(), nullable=False),
    sa.Column('username', sa.String(length=255), nullable=True),
    sa.Column('first_name', sa.String(length=255), nullable=True),
    sa.Column('last_name', sa.String(length=255), nullable=True),
    sa.Column('phone', sa.String(length=50), nullable=True),
    sa.Column('age', sa.Integer(), nullable=True),
    sa.Column('gender', sa.String(length=20), nullable=True),
    sa.Column('city', sa.String(length=100), nullable=True),
    sa.Column('occupation', sa.String(length=50), nullable=True),
    sa.Column('preferred_gender', sa.String(length=20), nullable=True),
    sa.Column('role', sa.String(length=20), nullable=True),
    sa.Column('language', sa.String(length=10), nullable=True),
    sa.Column('is_verified', sa.Boolean(), nullable=True),
    sa.Column('is_phone_verified', sa.Boolean(), nullable=True),
    sa.Column('is_blocked', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_telegram_id'), 'users', ['telegram_id'], unique=True)
    op.create_table('likes',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('from_user_id', sa.Integer(), nullable=False),
    sa.Column('target_type', sa.String(length=20), nullable=False),
    sa.Column('target_id', sa.Integer(), nullable=False),
    sa.Column('is_like', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['from_user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('listings',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('owner_id', sa.Integer(), nullable=False),
    sa.Column('city', sa.String(length=100), nullable=True),
    sa.Column('district', sa.String(length=100), nullable=False),
    sa.Column('address_landmark', sa.String(length=255), nullable=True),
    sa.Column('housing_type', sa.String(length=50), nullable=True),
    sa.Column('total_rooms', sa.Integer(), nullable=True),
    sa.Column('total_price', sa.Integer(), nullable=True),
    sa.Column('price_per_person', sa.Integer(), nullable=False),
    sa.Column('utilities_included', sa.Boolean(), nullable=True),
    sa.Column('deposit_amount', sa.Integer(), nullable=True),
    sa.Column('move_in_date', sa.String(length=100), nullable=True),
    sa.Column('available_places', sa.Integer(), nullable=True),
    sa.Column('occupied_places', sa.Integer(), nullable=True),
    sa.Column('current_gender', sa.String(length=20), nullable=True),
    sa.Column('preferred_gender', sa.String(length=20), nullable=True),
    sa.Column('smoking_allowed', sa.Boolean(), nullable=True),
    sa.Column('pets_allowed', sa.Boolean(), nullable=True),
    sa.Column('conditions_description', sa.Text(), nullable=True),
    sa.Column('lease_term', sa.String(length=100), nullable=True),
    sa.Column('preferred_age_range', sa.String(length=100), nullable=True),
    sa.Column('utilities_status', sa.String(length=50), nullable=True),
    sa.Column('utilities_amount', sa.Integer(), nullable=True),
    sa.Column('neighbor_criteria', sa.JSON(), nullable=True),
    sa.Column('photos', sa.JSON(), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=True),
    sa.Column('is_verified', sa.Boolean(), nullable=True),
    sa.Column('is_urgent', sa.Boolean(), nullable=True),
    sa.Column('last_confirmed_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_listings_district'), 'listings', ['district'], unique=False)
    op.create_index(op.f('ix_listings_status'), 'listings', ['status'], unique=False)
    op.create_table('reports',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('reporter_id', sa.Integer(), nullable=False),
    sa.Column('target_type', sa.String(length=20), nullable=False),
    sa.Column('target_id', sa.Integer(), nullable=False),
    sa.Column('reason', sa.String(length=50), nullable=True),
    sa.Column('details', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['reporter_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('saved_searches',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('districts', sa.JSON(), nullable=True),
    sa.Column('budget_max', sa.Integer(), nullable=True),
    sa.Column('move_in_date', sa.String(length=100), nullable=True),
    sa.Column('notify_active', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('seeker_profiles',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=True),
    sa.Column('age', sa.Integer(), nullable=True),
    sa.Column('gender', sa.String(length=20), nullable=True),
    sa.Column('city', sa.String(length=100), nullable=True),
    sa.Column('districts', sa.JSON(), nullable=True),
    sa.Column('budget_max', sa.Integer(), nullable=True),
    sa.Column('move_in_date', sa.String(length=100), nullable=True),
    sa.Column('spots_needed', sa.Integer(), nullable=True),
    sa.Column('housing_types', sa.JSON(), nullable=True),
    sa.Column('smoking', sa.String(length=20), nullable=True),
    sa.Column('alcohol', sa.String(length=20), nullable=True),
    sa.Column('pets', sa.String(length=20), nullable=True),
    sa.Column('occupation', sa.String(length=50), nullable=True),
    sa.Column('preferred_gender', sa.String(length=20), nullable=True),
    sa.Column('has_apartment', sa.Boolean(), nullable=True),
    sa.Column('apartment_address', sa.String(length=255), nullable=True),
    sa.Column('rooms_count', sa.String(length=50), nullable=True),
    sa.Column('room_type', sa.String(length=50), nullable=True),
    sa.Column('neighbors_needed', sa.Integer(), nullable=True),
    sa.Column('preferred_room_type', sa.String(length=50), nullable=True),
    sa.Column('budget_range', sa.String(length=100), nullable=True),
    sa.Column('ideal_neighbor_desc', sa.Text(), nullable=True),
    sa.Column('about_self_desc', sa.Text(), nullable=True),
    sa.Column('neighbor_criteria', sa.JSON(), nullable=True),
    sa.Column('notifications_enabled', sa.Boolean(), nullable=True),
    sa.Column('neighbor_preferences', sa.Text(), nullable=True),
    sa.Column('raw_bio', sa.Text(), nullable=True),
    sa.Column('is_urgent', sa.Boolean(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id')
    )
    op.create_table('matches',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('seeker_user_id', sa.Integer(), nullable=False),
    sa.Column('listing_id', sa.Integer(), nullable=False),
    sa.Column('owner_user_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=True),
    sa.Column('matched_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['listing_id'], ['listings.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['owner_user_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['seeker_user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    for table in ("matches", "saved_searches", "reports", "likes", "seeker_profiles", "listings", "users", "settings"):
        op.drop_table(table)
