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

class TwitchStreams(Base):
    """Twitch streams."""
    __tablename__ = "twitch_streams"

    id = Column(Integer, primary_key=True, autoincrement=True)