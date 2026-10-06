"""Seed flag, candidate/funnel events, freshness reminders.

- users.is_seed: fake test profiles; old seeds are detected and marked.
- seeker_profiles.last_freshness_ping_at: "still searching?" reminders.
- candidate_events: already shown / already notified candidates.
- funnel_events: admin funnel analytics.

Some of these may already exist in databases created by create_all() during
development, so every step checks first.

Revision ID: 0002_seeds_events_freshness
Revises: 0001_baseline
Create Date: 2026-10-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_seeds_events_freshness"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Before seeds were flagged they used small positive telegram ids (100001.., 200000..)
# and were always created with is_verified=True. Real Telegram ids are far larger.
OLD_SEED_MAX_TELEGRAM_ID = 10_000_000


def _columns(table: str) -> set:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _tables() -> set:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _indexes(table: str) -> set:
    return {i["name"] for i in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    tables = _tables()

    if "funnel_events" not in tables:
        op.create_table(
            "funnel_events",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("telegram_id", sa.BigInteger(), nullable=False),
            sa.Column("name", sa.String(length=64), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("telegram_id", "name", name="uq_funnel_event"),
        )
        op.create_index(op.f("ix_funnel_events_name"), "funnel_events", ["name"], unique=False)
        op.create_index(op.f("ix_funnel_events_telegram_id"), "funnel_events", ["telegram_id"], unique=False)

    if "candidate_events" not in tables:
        op.create_table(
            "candidate_events",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("viewer_user_id", sa.Integer(), nullable=False),
            sa.Column("candidate_user_id", sa.Integer(), nullable=False),
            sa.Column("kind", sa.String(length=20), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["candidate_user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["viewer_user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("viewer_user_id", "candidate_user_id", "kind", name="uq_candidate_event"),
        )
        op.create_index(
            op.f("ix_candidate_events_viewer_user_id"), "candidate_events", ["viewer_user_id"], unique=False
        )

    if "last_freshness_ping_at" not in _columns("seeker_profiles"):
        op.add_column("seeker_profiles", sa.Column("last_freshness_ping_at", sa.DateTime(), nullable=True))

    if "is_seed" not in _columns("users"):
        with op.batch_alter_table("users") as batch:
            batch.add_column(sa.Column("is_seed", sa.Boolean(), nullable=False, server_default=sa.false()))
        # Mark seeds created before the flag existed and drop their made-up usernames
        # (a made-up @username may belong to a real person).
        op.execute(
            sa.text(
                "UPDATE users SET is_seed = :t, username = NULL "
                "WHERE telegram_id > 0 AND telegram_id < :max_id AND is_verified = :t"
            ).bindparams(t=True, max_id=OLD_SEED_MAX_TELEGRAM_ID)
        )
    if op.f("ix_users_is_seed") not in _indexes("users"):
        op.create_index(op.f("ix_users_is_seed"), "users", ["is_seed"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_users_is_seed"), table_name="users")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("is_seed")
    with op.batch_alter_table("seeker_profiles") as batch:
        batch.drop_column("last_freshness_ping_at")
    op.drop_table("candidate_events")
    op.drop_table("funnel_events")
