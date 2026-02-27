import axios from "axios";
import { supabase, isSupabaseConfigured } from "../context/AuthContext";

const BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000";
const LOCAL_DEV = process.env.EXPO_PUBLIC_LOCAL_DEV === "true";

export const api = axios.create({
  baseURL: BASE_URL,
  timeout: 30_000,
});

// Attach Supabase JWT when configured (production).
// In LOCAL_DEV mode, no token is sent — the backend LOCAL_DEV bypass handles auth.
api.interceptors.request.use(async (config) => {
  if (!LOCAL_DEV && isSupabaseConfigured) {
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token;
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// ---------------------------------------------------------------------------
// Items
// ---------------------------------------------------------------------------

export interface Item {
  id: number;
  title: string | null;
  description: string | null;
  proposed_description: string | null;
  category: string | null;
  brand: string | null;
  condition: string | null;
  suggested_price: number | null;
  final_price: number | null;
  status: string;
  image_paths: string | null;
  created_at: string;
  listings: Listing[];
}

export interface Listing {
  id: number;
  platform: string;
  platform_url: string | null;
  price: number | null;
  status: string;
}

export interface Offer {
  id: number;
  amount: number;
  status: string;
  buyer_username: string | null;
  counter_amount: number | null;
  received_at: string;
}

export const getItems = () => api.get<Item[]>("/api/items").then((r) => r.data);

export const getItem = (id: number) =>
  api.get<Item>(`/api/items/${id}`).then((r) => r.data);

export const getOffers = (itemId: number) =>
  api.get<Offer[]>(`/api/items/${itemId}/offers`).then((r) => r.data);

export const approveItem = (itemId: number, finalPrice: number, description?: string) => {
  const params: Record<string, string> = { final_price: String(finalPrice) };
  if (description !== undefined) params.description = description;
  return api.post(`/api/items/${itemId}/approve`, null, { params }).then((r) => r.data);
};

export const cancelItem = (itemId: number) =>
  api.post(`/api/items/${itemId}/cancel`).then((r) => r.data);

export const delistListing = (listingId: number) =>
  api.post(`/api/listings/${listingId}/delist`).then((r) => r.data);

export const decideOffer = (
  offerId: number,
  action: "accept" | "decline" | "counter",
  counterAmount?: number
) =>
  api
    .post(`/api/offers/${offerId}/decide`, { action, counter_amount: counterAmount })
    .then((r) => r.data);

export const createItem = async (
  imageUris: string[],
  description: string,
  platforms: string
) => {
  const form = new FormData();
  form.append("description", description);
  form.append("platforms", platforms);
  for (const uri of imageUris) {
    const filename = uri.split("/").pop() ?? "photo.jpg";
    const match = /\.(\w+)$/.exec(filename);
    const type = match ? `image/${match[1]}` : "image/jpeg";
    form.append("images", { uri, name: filename, type } as any);
  }
  return api
    .post<Item>("/api/items", form, {
      headers: { "Content-Type": "multipart/form-data" },
    })
    .then((r) => r.data);
};
