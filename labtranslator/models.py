from datetime import datetime, timezone
from sqlalchemy import ForeignKey, String, Text, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class LabTerm(Base):
    __tablename__ = 'lab_terms'
    id: Mapped[int] = mapped_column(primary_key=True)
    japanese_name: Mapped[str] = mapped_column(String(200))
    normalized_name: Mapped[str] = mapped_column(String(200), unique=True)
    english_name: Mapped[str] = mapped_column(String(200))
    specimen_type: Mapped[str] = mapped_column(default='')
    seed_key: Mapped[str | None] = mapped_column(unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class Alias(Base):
    __tablename__ = 'lab_term_aliases'
    id: Mapped[int] = mapped_column(primary_key=True)
    term_id: Mapped[int] = mapped_column(ForeignKey('lab_terms.id'))
    alias_name: Mapped[str] = mapped_column(String(200))
    normalized_alias: Mapped[str] = mapped_column(String(200), unique=True)
    english_name: Mapped[str] = mapped_column(default='')
    specimen_type: Mapped[str] = mapped_column(default='')
    seed_key: Mapped[str | None] = mapped_column(unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class History(Base):
    __tablename__ = 'term_change_history'
    id: Mapped[int] = mapped_column(primary_key=True)
    target_table: Mapped[str]
    target_id: Mapped[int]
    action: Mapped[str]
    before_data: Mapped[str] = mapped_column(Text)
    after_data: Mapped[str] = mapped_column(Text)
    changed_by: Mapped[str]
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=now)
