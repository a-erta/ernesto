from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Float, DateTime, ForeignKey, Text, Enum as SAEnum
from datetime import datetime, timezone
from typing import Optional, List
import enum

from ..config import settings


engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


class ItemStatusEnum(str, enum.Enum):
    draft = "draft"
    analyzing = "analyzing"
    ready = "ready"
    publishing = "publishing"
    listed = "listed"
    sold = "sold"
    archived = "archived"


class ListingStatusEnum(str, enum.Enum):
    draft = "draft"
    published = "published"
    ended = "ended"
    sold = "sold"


class OfferStatusEnum(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    declined = "declined"
    countered = "countered"
    expired = "expired"


class PlatformEnum(str, enum.Enum):
    ebay = "ebay"
    vinted = "vinted"
    depop = "depop"


class DBItem(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[Optional[str]] = mapped_column(String(200))
    description: Mapped[Optional[str]] = mapped_column(Text)
    category: Mapped[Optional[str]] = mapped_column(String(100))
    brand: Mapped[Optional[str]] = mapped_column(String(100))
    model: Mapped[Optional[str]] = mapped_column(String(100))
    condition: Mapped[Optional[str]] = mapped_column(String(50))
    size: Mapped[Optional[str]] = mapped_column(String(50))
    color: Mapped[Optional[str]] = mapped_column(String(50))
    user_description: Mapped[Optional[str]] = mapped_column(Text)
    image_paths: Mapped[Optional[str]] = mapped_column(Text)  # JSON list
    suggested_price: Mapped[Optional[float]] = mapped_column(Float)
    final_price: Mapped[Optional[float]] = mapped_column(Float)
    status: Mapped[ItemStatusEnum] = mapped_column(
        SAEnum(ItemStatusEnum), default=ItemStatusEnum.draft
    )
    ai_analysis: Mapped[Optional[str]] = mapped_column(Text)  # JSON blob
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    listings: Mapped[List["DBListing"]] = relationship(back_populates="item", cascade="all, delete-orphan")
    comparables: Mapped[List["DBComparable"]] = relationship(back_populates="item", cascade="all, delete-orphan")


class DBListing(Base):
    __tablename__ = "listings"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    platform: Mapped[PlatformEnum] = mapped_column(SAEnum(PlatformEnum))
    platform_listing_id: Mapped[Optional[str]] = mapped_column(String(200))
    platform_url: Mapped[Optional[str]] = mapped_column(String(500))
    title: Mapped[Optional[str]] = mapped_column(String(200))
    description: Mapped[Optional[str]] = mapped_column(Text)
    price: Mapped[Optional[float]] = mapped_column(Float)
    status: Mapped[ListingStatusEnum] = mapped_column(
        SAEnum(ListingStatusEnum), default=ListingStatusEnum.draft
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    item: Mapped["DBItem"] = relationship(back_populates="listings")
    offers: Mapped[List["DBOffer"]] = relationship(back_populates="listing", cascade="all, delete-orphan")
    messages: Mapped[List["DBMessage"]] = relationship(back_populates="listing", cascade="all, delete-orphan")


class DBOffer(Base):
    __tablename__ = "offers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"))
    platform_offer_id: Mapped[Optional[str]] = mapped_column(String(200))
    buyer_username: Mapped[Optional[str]] = mapped_column(String(200))
    amount: Mapped[float] = mapped_column(Float)
    status: Mapped[OfferStatusEnum] = mapped_column(
        SAEnum(OfferStatusEnum), default=OfferStatusEnum.pending
    )
    counter_amount: Mapped[Optional[float]] = mapped_column(Float)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    listing: Mapped["DBListing"] = relationship(back_populates="offers")


class DBMessage(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"))
    platform_message_id: Mapped[Optional[str]] = mapped_column(String(200))
    buyer_username: Mapped[Optional[str]] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    direction: Mapped[str] = mapped_column(String(10))  # 'inbound' | 'outbound'
    auto_replied: Mapped[bool] = mapped_column(default=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    listing: Mapped["DBListing"] = relationship(back_populates="messages")


class DBComparable(Base):
    __tablename__ = "comparables"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    platform: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(300))
    sold_price: Mapped[float] = mapped_column(Float)
    url: Mapped[Optional[str]] = mapped_column(String(500))
    sold_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    condition: Mapped[Optional[str]] = mapped_column(String(50))

    item: Mapped["DBItem"] = relationship(back_populates="comparables")
