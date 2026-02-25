from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime


@dataclass
class ListingDraft:
    title: str
    description: str
    price: float
    category_id: str
    condition: str
    image_paths: List[str] = field(default_factory=list)
    shipping_options: List[dict] = field(default_factory=list)
    extra: dict = field(default_factory=dict)


@dataclass
class PlatformOffer:
    platform_offer_id: str
    listing_id: str
    buyer_username: str
    amount: float
    received_at: datetime
    message: Optional[str] = None


@dataclass
class PlatformMessage:
    platform_message_id: str
    listing_id: str
    buyer_username: str
    content: str
    received_at: datetime


@dataclass
class PublishedListing:
    platform_listing_id: str
    platform_url: str


class BasePlatformAdapter(ABC):
    """
    Abstract adapter every platform must implement.
    Keeps agents completely platform-agnostic.
    """

    @property
    @abstractmethod
    def platform_name(self) -> str: ...

    @abstractmethod
    async def post_listing(self, draft: ListingDraft) -> PublishedListing: ...

    @abstractmethod
    async def update_listing(self, platform_listing_id: str, draft: ListingDraft) -> bool: ...

    @abstractmethod
    async def end_listing(self, platform_listing_id: str) -> bool: ...

    @abstractmethod
    async def get_offers(self, platform_listing_id: str) -> List[PlatformOffer]: ...

    @abstractmethod
    async def accept_offer(self, platform_offer_id: str) -> bool: ...

    @abstractmethod
    async def decline_offer(self, platform_offer_id: str) -> bool: ...

    @abstractmethod
    async def counter_offer(self, platform_offer_id: str, amount: float) -> bool: ...

    @abstractmethod
    async def get_messages(self, platform_listing_id: str) -> List[PlatformMessage]: ...

    @abstractmethod
    async def send_message(self, platform_listing_id: str, buyer_username: str, content: str) -> bool: ...

    @abstractmethod
    async def get_sold_comparables(self, query: str, limit: int = 10) -> List[dict]: ...

    @abstractmethod
    async def mark_sold(self, platform_listing_id: str) -> bool: ...
