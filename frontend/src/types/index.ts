export type ItemStatus =
  | "draft"
  | "analyzing"
  | "ready"
  | "publishing"
  | "listed"
  | "sold"
  | "archived";

export type ListingStatus = "draft" | "published" | "ended" | "sold";
export type OfferStatus = "pending" | "accepted" | "declined" | "countered" | "expired";
export type Platform = "ebay" | "vinted" | "depop";

export interface Comparable {
  id: number;
  item_id: number;
  platform: string;
  title: string;
  sold_price: number;
  url?: string;
  sold_at?: string;
  condition?: string;
}

export interface Offer {
  id: number;
  listing_id: number;
  platform_offer_id?: string;
  buyer_username?: string;
  amount: number;
  status: OfferStatus;
  counter_amount?: number;
  notes?: string;
  received_at: string;
  resolved_at?: string;
}

export interface Message {
  id: number;
  listing_id: number;
  platform_message_id?: string;
  buyer_username?: string;
  content: string;
  direction: "inbound" | "outbound";
  auto_replied: boolean;
  received_at: string;
}

export interface Listing {
  id: number;
  item_id: number;
  platform: Platform;
  platform_listing_id?: string;
  platform_url?: string;
  title?: string;
  description?: string;
  price?: number;
  status: ListingStatus;
  published_at?: string;
  created_at: string;
  offers: Offer[];
  messages: Message[];
}

export interface Item {
  id: number;
  title?: string;
  description?: string;
  category?: string;
  brand?: string;
  model?: string;
  condition?: string;
  size?: string;
  color?: string;
  user_description?: string;
  image_paths?: string;
  suggested_price?: number;
  final_price?: number;
  status: ItemStatus;
  ai_analysis?: string;
  created_at: string;
  updated_at: string;
  listings: Listing[];
  comparables: Comparable[];
}

export interface AgentEvent {
  type: "step" | "resumed" | "error";
  step?: string;
  item_id: number;
  data?: Record<string, unknown>;
}
