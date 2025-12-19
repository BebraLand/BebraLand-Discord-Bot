"""
SQLAlchemy models for the Discord bot database.
"""
from sqlalchemy import Column, String, Integer, BigInteger, Float, Text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class UserLanguage(Base):
    """User language preferences."""
    __tablename__ = "user_languages"

    user_id = Column(String(255), primary_key=True)
    language = Column(String(10), nullable=False)


class ScheduledTask(Base):
    """Scheduled tasks for the bot."""
    __tablename__ = "scheduled_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(String(50), nullable=False)
    guild_id = Column(BigInteger, nullable=True)
    channel_id = Column(BigInteger, nullable=True)
    time = Column(String(10), nullable=False)
    run_at = Column(Float, nullable=False)
    payload = Column(Text, nullable=True)


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


class TwitchStreamState(Base):
    """Track Twitch stream states to handle live notifications."""
    __tablename__ = "twitch_stream_states"

    twitch_username = Column(String(255), primary_key=True)
    is_live = Column(Integer, nullable=False, default=0)  # 0 = offline, 1 = live
    stream_id = Column(String(255), nullable=True)  # Twitch stream ID
    notification_message_id = Column(BigInteger, nullable=True)  # Discord message ID to delete when stream ends
    started_at = Column(String(255), nullable=True)  # ISO timestamp when stream started
    last_checked = Column(Float, nullable=False)  # Unix timestamp of last check


class TempVoiceChannel(Base):
    """Temporary voice channels created by users."""
    __tablename__ = "temp_voice_channels"

    channel_id = Column(BigInteger, primary_key=True)  # Discord channel ID
    owner_id = Column(String(255), nullable=False)  # Discord user ID of the owner
    guild_id = Column(BigInteger, nullable=False)  # Discord guild ID
    created_at = Column(Float, nullable=False)  # Unix timestamp when created
    control_message_id = Column(BigInteger, nullable=True)  # Discord message ID of control panel
    # JSON field to store permitted/rejected user IDs
    permitted_users = Column(Text, nullable=True, default="[]")  # JSON array of user IDs
    rejected_users = Column(Text, nullable=True, default="[]")  # JSON array of user IDs
    is_locked = Column(Integer, nullable=False, default=0)  # 0 = unlocked, 1 = locked
    is_ghost = Column(Integer, nullable=False, default=0)  # 0 = visible, 1 = invisible