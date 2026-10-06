"""Database models for KORSHI TAP."""

from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.constants import (
    DEFAULT_CITY,
    GENDER_ANY,
    LISTING_STATUS_ACTIVE,
    MATCH_STATUS_MATCHED,
    REPORT_REASON_OTHER,
    ROLE_SEEKER,
)
from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    age = Column(Integer, nullable=True)
    gender = Column(String(20), nullable=True)
    city = Column(String(100), default=DEFAULT_CITY, nullable=True)
    occupation = Column(String(50), default="student")  # "student", "working", "both"
    preferred_gender = Column(String(20), default="any")  # "female", "male", "any"
    role = Column(String(20), default=ROLE_SEEKER)  # seeker, owner, both
    language = Column(String(10), default="kz")  # 'kz' or 'ru' (kz is primary)
    is_verified = Column(Boolean, default=False)
    is_phone_verified = Column(Boolean, default=False)
    is_blocked = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    seeker_profile = relationship("SeekerProfile", back_populates="user", uselist=False)
    listings = relationship("Listing", back_populates="owner", cascade="all, delete-orphan")
    likes_sent = relationship("Like", back_populates="from_user", foreign_keys="Like.from_user_id")
    reports_sent = relationship("Report", back_populates="reporter", foreign_keys="Report.reporter_id")


class SeekerProfile(Base):
    __tablename__ = "seeker_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    name = Column(String(255), nullable=True)
    age = Column(Integer, nullable=True)
    gender = Column(String(20), nullable=True)
    city = Column(String(100), default=DEFAULT_CITY)
    districts = Column(JSON, default=list)  # e.g. ["Бостандыкский", "Алмалинский"]
    budget_max = Column(Integer, default=120000)
    move_in_date = Column(String(100), nullable=True)
    spots_needed = Column(Integer, default=1)  # 1, 2, 3+
    housing_types = Column(JSON, default=list)  # ["room", "spot", "sharing"]
    smoking = Column(String(20), default="no")
    alcohol = Column(String(20), default="neutral")
    pets = Column(String(20), default="no")
    occupation = Column(String(50), default="student")  # student, working, other
    preferred_gender = Column(String(20), default=GENDER_ANY)
    has_apartment = Column(Boolean, default=False)
    apartment_address = Column(String(255), nullable=True)
    rooms_count = Column(String(50), nullable=True)          # e.g. "2-комнатная", "1-бөлмелі"
    room_type = Column(String(50), nullable=True)            # "separate" vs "shared"
    neighbors_needed = Column(Integer, default=1)            # How many roommates needed
    preferred_room_type = Column(String(50), default="any")  # For seekers without flat: separate, shared, any
    budget_range = Column(String(100), nullable=True)
    ideal_neighbor_desc = Column(Text, nullable=True)
    about_self_desc = Column(Text, nullable=True)
    neighbor_criteria = Column(JSON, default=dict)
    notifications_enabled = Column(Boolean, default=True)
    neighbor_preferences = Column(Text, nullable=True)
    raw_bio = Column(Text, nullable=True)
    is_urgent = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="seeker_profile")


class Listing(Base):
    __tablename__ = "listings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    city = Column(String(100), default=DEFAULT_CITY)
    district = Column(String(100), nullable=False, index=True)
    address_landmark = Column(String(255), nullable=True)
    housing_type = Column(String(50), default="room")  # room, flat, spot, sharing
    total_rooms = Column(Integer, default=2)
    total_price = Column(Integer, nullable=True)
    price_per_person = Column(Integer, nullable=False)
    utilities_included = Column(Boolean, default=False)
    deposit_amount = Column(Integer, default=0)
    move_in_date = Column(String(100), nullable=True)
    available_places = Column(Integer, default=1)  # Multiple available spots support
    occupied_places = Column(Integer, default=1)
    current_gender = Column(String(20), default="mixed")
    preferred_gender = Column(String(20), default=GENDER_ANY)
    smoking_allowed = Column(Boolean, default=False)
    pets_allowed = Column(Boolean, default=False)
    conditions_description = Column(Text, nullable=True)
    lease_term = Column(String(100), nullable=True)
    preferred_age_range = Column(String(100), nullable=True)
    utilities_status = Column(String(50), nullable=True)  # included, separate, unknown
    utilities_amount = Column(Integer, nullable=True)
    neighbor_criteria = Column(JSON, default=dict)
    photos = Column(JSON, default=list)  # Telegram file_ids or URLs
    status = Column(String(20), default=LISTING_STATUS_ACTIVE, index=True)
    is_verified = Column(Boolean, default=False)
    is_urgent = Column(Boolean, default=False)
    last_confirmed_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = relationship("User", back_populates="listings")
    matches = relationship("Match", back_populates="listing", cascade="all, delete-orphan")


class Like(Base):
    """Stores user swipes: Like (True) or Pass (False)."""
    __tablename__ = "likes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    from_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    target_type = Column(String(20), nullable=False)  # 'listing' or 'seeker'
    target_id = Column(Integer, nullable=False)        # listing_id or seeker_user_id
    is_like = Column(Boolean, default=True)            # True=Like, False=Pass
    created_at = Column(DateTime, default=datetime.utcnow)

    from_user = relationship("User", back_populates="likes_sent", foreign_keys=[from_user_id])


class Match(Base):
    """Mutual match between seeker and listing/owner."""
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    seeker_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    listing_id = Column(Integer, ForeignKey("listings.id", ondelete="CASCADE"), nullable=False)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), default=MATCH_STATUS_MATCHED)  # matched, contacted, archived
    matched_at = Column(DateTime, default=datetime.utcnow)

    seeker_user = relationship("User", foreign_keys=[seeker_user_id])
    owner_user = relationship("User", foreign_keys=[owner_user_id])
    listing = relationship("Listing", back_populates="matches")


class Report(Base):
    """Complaints submitted by users."""
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reporter_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    target_type = Column(String(20), nullable=False)  # 'listing' or 'user'
    target_id = Column(Integer, nullable=False)
    reason = Column(String(50), default=REPORT_REASON_OTHER)
    details = Column(Text, nullable=True)
    status = Column(String(20), default="pending")  # pending, reviewed, dismissed
    created_at = Column(DateTime, default=datetime.utcnow)

    reporter = relationship("User", back_populates="reports_sent", foreign_keys=[reporter_id])


class SavedSearch(Base):
    """Saved search criteria for notifications when new listings appear."""
    __tablename__ = "saved_searches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    districts = Column(JSON, default=list)
    budget_max = Column(Integer, nullable=True)
    move_in_date = Column(String(100), nullable=True)
    notify_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")


class Setting(Base):
    """Global dynamic settings editable via Admin Panel."""
    __tablename__ = "settings"

    key = Column(String(100), primary_key=True)
    value = Column(JSON, nullable=False)
    description = Column(String(255), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
