import axios from "axios";
import type { Item, Listing, Offer, Message } from "../types";
import { supabase, isSupabaseConfigured } from "./supabase";

// When deploying frontend separately (e.g. static site), set VITE_API_URL to your backend origin
// e.g. https://ernesto-w0b2.onrender.com — requests will go to {VITE_API_URL}/api
const apiBase =
  typeof import.meta.env.VITE_API_URL === "string" && import.meta.env.VITE_API_URL
    ? `${import.meta.env.VITE_API_URL.replace(/\/$/, "")}/api`
    : "/api";

const api = axios.create({ baseURL: apiBase });

/** Backend origin (for health check and links that must point at API host). */
export function getBackendOrigin(): string {
  if (typeof import.meta.env.VITE_API_URL === "string" && import.meta.env.VITE_API_URL) {
    try {
      return new URL(import.meta.env.VITE_API_URL).origin;
    } catch {
      return typeof window !== "undefined" ? window.location.origin : "";
    }
  }
  return typeof window !== "undefined" ? window.location.origin : "";
}

export type BackendHealth = { ok: true } | { ok: false; message: string };

const fetchOpts = { method: "GET" as const, credentials: "omit" as const };

/** Ping backend (GET / or GET /docs). Returns { ok, message? } for UI. */
export async function checkBackendHealth(): Promise<BackendHealth> {
  const origin = getBackendOrigin().replace(/\/$/, "");
  if (!origin) return { ok: false, message: "No backend URL configured" };

  try {
    const resRoot = await fetch(`${origin}/`, fetchOpts);
    const data = await resRoot.json().catch(() => ({}));
    if (resRoot.ok && data?.health === "ok") return { ok: true };
    // If root 404s (e.g. old deploy), try /docs which FastAPI always serves
    if (resRoot.status === 404) {
      const resDocs = await fetch(`${origin}/docs`, fetchOpts);
      if (resDocs.ok) return { ok: true };
    }
    return {
      ok: false,
      message: (data?.detail as string) || resRoot.statusText || `HTTP ${resRoot.status}`,
    };
  } catch (e) {
    const message = e instanceof Error ? e.message : "Unreachable";
    return { ok: false, message };
  }
}

// Attach Supabase JWT when Supabase is configured (production).
// In local dev (no Supabase), no Authorization header is sent and the backend
// LOCAL_DEV bypass handles auth transparently.
api.interceptors.request.use(async (config) => {
  if (isSupabaseConfigured) {
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token;
    if (token) {
      config.headers = config.headers ?? {};
      config.headers["Authorization"] = `Bearer ${token}`;
    }
  }
  return config;
});

export const itemsApi = {
  list: () => api.get<Item[]>("/items").then((r) => r.data),
  get: (id: number) => api.get<Item>(`/items/${id}`).then((r) => r.data),
  create: (form: FormData) =>
    api.post<Item>("/items", form, {
      headers: { "Content-Type": "multipart/form-data" },
    }).then((r) => r.data),
  delete: (id: number) => api.delete(`/items/${id}`).then((r) => r.data),
  approve: (id: number, finalPrice: number, description?: string) => {
    const params = new URLSearchParams({ final_price: String(finalPrice) });
    if (description !== undefined) params.set("description", description);
    return api.post(`/items/${id}/approve?${params}`).then((r) => r.data);
  },
  cancel: (id: number) => api.post(`/items/${id}/cancel`).then((r) => r.data),
  getListings: (id: number) =>
    api.get<Listing[]>(`/items/${id}/listings`).then((r) => r.data),
  delist: (listingId: number) =>
    api.post(`/listings/${listingId}/delist`).then((r) => r.data),
  getOffers: (id: number) =>
    api.get<Offer[]>(`/items/${id}/offers`).then((r) => r.data),
  getMessages: (id: number) =>
    api.get<Message[]>(`/items/${id}/messages`).then((r) => r.data),
};

export const offersApi = {
  decide: (
    offerId: number,
    decision: { action: string; counter_amount?: number; notes?: string }
  ) => api.post(`/offers/${offerId}/decide`, decision).then((r) => r.data),
};
