import { clsx } from "clsx";
import type { ItemStatus, OfferStatus, ListingStatus } from "../types";

const itemColors: Record<ItemStatus, string> = {
  draft: "bg-slate-700 text-slate-300",
  analyzing: "bg-yellow-500/20 text-yellow-300 animate-pulse",
  ready: "bg-blue-500/20 text-blue-300",
  publishing: "bg-purple-500/20 text-purple-300 animate-pulse",
  listed: "bg-green-500/20 text-green-300",
  sold: "bg-emerald-500/20 text-emerald-300",
  archived: "bg-slate-700 text-slate-500",
};

const offerColors: Record<OfferStatus, string> = {
  pending: "bg-yellow-500/20 text-yellow-300",
  accepted: "bg-green-500/20 text-green-300",
  declined: "bg-red-500/20 text-red-300",
  countered: "bg-blue-500/20 text-blue-300",
  expired: "bg-slate-700 text-slate-500",
};

const listingColors: Record<ListingStatus, string> = {
  draft: "bg-slate-700 text-slate-300",
  published: "bg-green-500/20 text-green-300",
  ended: "bg-slate-700 text-slate-500",
  sold: "bg-emerald-500/20 text-emerald-300",
};

interface Props {
  status: ItemStatus | OfferStatus | ListingStatus;
  type?: "item" | "offer" | "listing";
}

export function StatusBadge({ status, type = "item" }: Props) {
  const colorMap =
    type === "offer" ? offerColors : type === "listing" ? listingColors : itemColors;
  const color = (colorMap as Record<string, string>)[status] ?? "bg-slate-700 text-slate-300";
  return (
    <span className={clsx("badge", color)}>
      {status.replace("_", " ")}
    </span>
  );
}
