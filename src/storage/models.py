"""
SQLAlchemy models for the Discord bot database.
"""

from sqlalchemy import JSON, BigInteger, Boolean, Column, Float, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class UserLanguage(Base):
    """User language preferences."""

    __tablename__ = "user_languages"

    user_id = Column(String(255), primary_key=True)
    language = Column(String(10), nullable=False)


class Ticket(Base):
    """Support tickets."""

    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), nullable=False)
    issue = Column(Text, nullable=False)
    channel_id = Column(BigInteger, nullable=True)
    status = Column(String(20), nullable=False, default="open")
    created_at = Column(Float, nullable=False)
    closed_at = Column(Float, nullable=True)


class Application(Base):
    """Player applications for server verification."""

    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), nullable=False)
    guild_id = Column(BigInteger, nullable=False)
    answers = Column(JSON, nullable=False, default=list)
    status = Column(String(20), nullable=False, default="pending")
    review_channel_id = Column(BigInteger, nullable=True)
    review_message_id = Column(BigInteger, nullable=True)
    created_at = Column(Float, nullable=False)
    decided_at = Column(Float, nullable=True)
    decided_by = Column(String(255), nullable=True)
    decision_reason = Column(Text, nullable=True)


class Event(Base):
    """Server events with Discord panel metadata."""

    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=False)
    channel_id = Column(BigInteger, nullable=True)
    message_id = Column(BigInteger, nullable=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    starts_at = Column(Float, nullable=False)
    languages = Column(JSON, nullable=False, default=list)
    player_limit = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="open")
    created_by_id = Column(String(255), nullable=False)
    created_at = Column(Float, nullable=False)


class EventRegistration(Base):
    """Users registered for an event."""

    __tablename__ = "event_registrations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(Integer, nullable=False)
    user_id = Column(String(255), nullable=False)
    status = Column(String(20), nullable=False)
    position = Column(Integer, nullable=False)
    registered_at = Column(Float, nullable=False)
    added_by_id = Column(String(255), nullable=True)


class GuildSetting(Base):
    """Generic per-guild runtime settings."""

    __tablename__ = "guild_settings"

    guild_id = Column(BigInteger, primary_key=True)
    key = Column(String(255), primary_key=True)
    value = Column(JSON, nullable=False)


class TwitchStreamState(Base):
    """Track Twitch stream states to handle live notifications."""

    __tablename__ = "twitch_stream_states"

    twitch_username = Column(String(255), primary_key=True)
    is_live = Column(Integer, nullable=False, default=0)  # 0 = offline, 1 = live
    stream_id = Column(String(255), nullable=True)  # Twitch stream ID
    notification_message_id = Column(
        BigInteger, nullable=True
    )  # Discord message ID to delete when stream ends
    started_at = Column(String(255), nullable=True)  # ISO timestamp when stream started
    last_checked = Column(Float, nullable=False)  # Unix timestamp of last check


class TempVoiceChannel(Base):
    """Temporary voice channels created by users."""

    __tablename__ = "temp_voice_channels"

    channel_id = Column(BigInteger, primary_key=True)
    owner_id = Column(BigInteger, nullable=False)
    guild_id = Column(BigInteger, nullable=False)
    control_message_id = Column(
        BigInteger, nullable=True
    )  # ID of the control panel message
    created_at = Column(Float, nullable=False)
    permitted_users = Column(
        JSON, nullable=True, default=list
    )  # List of user IDs with special access
    permitted_roles = Column(
        JSON, nullable=True, default=list
    )  # List of role IDs with special access
    rejected_users = Column(
        JSON, nullable=True, default=list
    )  # List of blocked user IDs
    rejected_roles = Column(
        JSON, nullable=True, default=list
    )  # List of blocked role IDs


class TempVoiceInvites(Base):
    """Temp voice invites."""

    __tablename__ = "temp_voice_invites"

    user_id = Column(String(255), primary_key=True)
    blocked = Column(Boolean, nullable=False, default=False)
