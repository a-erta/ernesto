import axios from "axios";
import type { Item, Listing, Offer, Message } from "../types";

const api = axios.create({ baseURL: "/api" });

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
