from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, List
from enum import Enum


class Platform(str, Enum):
    ebay = "ebay"
    vinted = "vinted"
    depop = "depop"


class ItemStatus(str, Enum):
    draft = "draft"
    analyzing = "analyzing"
    ready = "ready"
    publishing = "publishing"
    listed = "listed"
    sold = "sold"
    archived = "archived"


class ListingStatus(str, Enum):
    draft = "draft"
    published = "published"
    ended = "ended"
    sold = "sold"


class OfferStatus(str, Enum):
    pending = "pending"
    accepted = "accepted"
    declined = "declined"
    countered = "countered"
    expired = "expired"


# --- Item ---

class ItemCreate(BaseModel):
    user_description: Optional[str] = None
    image_paths: Optional[List[str]] = None


class Item(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    condition: Optional[str] = None
    size: Optional[str] = None
    color: Optional[str] = None
    user_description: Optional[str] = None
    proposed_description: Optional[str] = None
    image_paths: Optional[str] = None
    suggested_price: Optional[float] = None
    final_price: Optional[float] = None
    status: ItemStatus
    ai_analysis: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    listings: List["Listing"] = []
    comparables: List["Comparable"] = []


# --- Listing ---

class ListingCreate(BaseModel):
    item_id: int
    platform: Platform
    price: Optional[float] = None


class Listing(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_id: int
    platform: Platform
    platform_listing_id: Optional[str] = None
    platform_url: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    status: ListingStatus
    published_at: Optional[datetime] = None
    created_at: datetime
    offers: List["Offer"] = []
    messages: List["Message"] = []


# --- Offer ---

class OfferCreate(BaseModel):
    listing_id: int
    platform_offer_id: Optional[str] = None
    buyer_username: Optional[str] = None
    amount: float


class OfferDecision(BaseModel):
    action: str  # 'accept' | 'decline' | 'counter'
    counter_amount: Optional[float] = None
    notes: Optional[str] = None


class Offer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    listing_id: int
    platform_offer_id: Optional[str] = None
    buyer_username: Optional[str] = None
    amount: float
    status: OfferStatus
    counter_amount: Optional[float] = None
    notes: Optional[str] = None
    received_at: datetime
    resolved_at: Optional[datetime] = None


# --- Message ---

class MessageCreate(BaseModel):
    listing_id: int
    platform_message_id: Optional[str] = None
    buyer_username: Optional[str] = None
    content: str
    direction: str


class Message(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    listing_id: int
    platform_message_id: Optional[str] = None
    buyer_username: Optional[str] = None
    content: str
    direction: str
    auto_replied: bool
    received_at: datetime


# --- Comparable ---

class Comparable(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_id: int
    platform: str
    title: str
    sold_price: float
    url: Optional[str] = None
    sold_at: Optional[datetime] = None
    condition: Optional[str] = None


# --- Agent State (used in LangGraph) ---

class AgentState(BaseModel):
    item_id: int
    step: str = "intake"
    item_data: Optional[dict] = None
    comparables: List[dict] = []
    listings: List[dict] = []
    errors: List[str] = []
    awaiting_human: bool = False
    human_input: Optional[dict] = None
    platforms: List[Platform] = [Platform.ebay]
