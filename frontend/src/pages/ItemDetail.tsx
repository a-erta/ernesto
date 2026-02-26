import { useParams, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ExternalLink, MessageSquare, Tag, AlertTriangle, XCircle } from "lucide-react";
import { itemsApi } from "../lib/api";
import { StatusBadge } from "../components/StatusBadge";
import { PlatformBadge } from "../components/PlatformIcon";
import { AgentTimeline } from "../components/AgentTimeline";
import { ApprovalPanel } from "../components/ApprovalPanel";
import { OfferCard } from "../components/OfferCard";
import { useItemSocket } from "../hooks/useItemSocket";
import type { AgentEvent, Platform } from "../types";

export function ItemDetail() {
  const { id } = useParams<{ id: string }>();
  const itemId = parseInt(id!, 10);
  const qc = useQueryClient();

  const delistMutation = useMutation({
    mutationFn: (listingId: number) => itemsApi.delist(listingId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["item", itemId] });
      qc.invalidateQueries({ queryKey: ["items"] });
    },
  });

  const { data: item, isLoading } = useQuery({
    queryKey: ["item", itemId],
    queryFn: () => itemsApi.get(itemId),
    refetchInterval: 8000,
  });

  const { data: offers = [] } = useQuery({
    queryKey: ["offers", itemId],
    queryFn: () => itemsApi.getOffers(itemId),
    refetchInterval: 10000,
    enabled: !!item && ["listed", "sold"].includes(item.status),
  });

  const { data: messages = [] } = useQuery({
    queryKey: ["messages", itemId],
    queryFn: () => itemsApi.getMessages(itemId),
    refetchInterval: 10000,
    enabled: !!item && ["listed", "sold"].includes(item.status),
  });

  useItemSocket(itemId, (event: AgentEvent) => {
    if (event.type === "step") {
      qc.invalidateQueries({ queryKey: ["item", itemId] });
      qc.invalidateQueries({ queryKey: ["offers", itemId] });
      qc.invalidateQueries({ queryKey: ["messages", itemId] });
    }
  });

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-48 bg-slate-800 rounded animate-pulse" />
        <div className="card h-40 animate-pulse bg-slate-800" />
      </div>
    );
  }

  if (!item) {
    return (
      <div className="card text-center py-16">
        <AlertTriangle className="w-8 h-8 mx-auto text-red-400 mb-2" />
        <p className="text-slate-400">Item not found.</p>
        <Link to="/" className="text-brand-400 text-sm mt-2 inline-block">← Back to dashboard</Link>
      </div>
    );
  }

  const images: string[] = (() => {
    try { return JSON.parse(item.image_paths || "[]"); } catch { return []; }
  })();

  const analysis = (() => {
    try { return JSON.parse(item.ai_analysis || "{}"); } catch { return {}; }
  })();

  const pendingOffers = offers.filter((o) => o.status === "pending");

  return (
    <div className="space-y-6 max-w-3xl">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Link to="/" className="text-slate-400 hover:text-white transition-colors">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div className="flex-1 min-w-0">
          <h1 className="text-xl font-bold truncate">
            {item.title || item.user_description || "Untitled item"}
          </h1>
          <p className="text-slate-400 text-sm">{item.category}</p>
        </div>
        <StatusBadge status={item.status} />
      </div>

      {/* Timeline */}
      <AgentTimeline status={item.status} />

      {/* Approval panel */}
      {item.status === "ready" && <ApprovalPanel item={item} />}

      {/* Pending offer alert */}
      {pendingOffers.length > 0 && (
        <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-xl p-4 flex items-center gap-3">
          <div className="w-2 h-2 rounded-full bg-yellow-400 animate-pulse flex-shrink-0" />
          <p className="text-yellow-300 text-sm font-medium">
            {pendingOffers.length} pending offer{pendingOffers.length > 1 ? "s" : ""} awaiting your decision
          </p>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Photos */}
        {images.length > 0 && (
          <div className="card space-y-3">
            <h3 className="font-medium text-sm text-slate-400">Photos</h3>
            <div className="grid grid-cols-3 gap-2">
              {images.map((path, i) => (
                <img
                  key={i}
                  src={`/uploads/${path.split("/").pop()}`}
                  alt=""
                  className="w-full aspect-square object-cover rounded-lg bg-slate-800"
                />
              ))}
            </div>
          </div>
        )}

        {/* Item details */}
        <div className="card space-y-3">
          <h3 className="font-medium text-sm text-slate-400">Item details</h3>
          <div className="space-y-2 text-sm">
            {[
              ["Brand", item.brand],
              ["Model", item.model],
              ["Condition", item.condition],
              ["Color", item.color],
              ["Size", item.size],
              ["Suggested price", item.suggested_price ? `$${item.suggested_price.toFixed(2)}` : null],
              ["Final price", item.final_price ? `$${item.final_price.toFixed(2)}` : null],
            ]
              .filter(([, v]) => v)
              .map(([label, value]) => (
                <div key={label as string} className="flex justify-between">
                  <span className="text-slate-500">{label}</span>
                  <span className="text-slate-200 font-medium">{value}</span>
                </div>
              ))}
          </div>
          {analysis.key_features?.length > 0 && (
            <div>
              <p className="text-xs text-slate-500 mb-1.5">Key features</p>
              <div className="flex flex-wrap gap-1.5">
                {analysis.key_features.map((f: string) => (
                  <span key={f} className="badge bg-slate-700 text-slate-300">{f}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Listings */}
      {item.listings.length > 0 && (
        <div className="card space-y-3">
          <h3 className="font-medium flex items-center gap-2">
            <Tag className="w-4 h-4 text-slate-400" /> Listings
          </h3>
          <div className="space-y-2">
            {item.listings.map((listing) => (
              <div key={listing.id} className="flex items-center justify-between bg-slate-800 rounded-lg px-4 py-3 gap-3">
                <div className="flex items-center gap-3 min-w-0">
                  <PlatformBadge platform={listing.platform as Platform} />
                  <span className="text-sm text-slate-300 truncate">{listing.title}</span>
                </div>
                <div className="flex items-center gap-3 flex-shrink-0">
                  {listing.price && (
                    <span className="text-green-400 font-medium text-sm">€{listing.price.toFixed(2)}</span>
                  )}
                  <StatusBadge status={listing.status} type="listing" />
                  {listing.platform_url && (
                    <a
                      href={listing.platform_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-slate-500 hover:text-slate-300 transition-colors"
                      title="View on platform"
                    >
                      <ExternalLink className="w-4 h-4" />
                    </a>
                  )}
                  {listing.status === "published" && (
                    <button
                      className="text-slate-500 hover:text-red-400 transition-colors disabled:opacity-40"
                      title="Delist from platform"
                      disabled={delistMutation.isPending}
                      onClick={() => {
                        if (confirm(`Remove this ${listing.platform} listing?`)) {
                          delistMutation.mutate(listing.id);
                        }
                      }}
                    >
                      <XCircle className="w-4 h-4" />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Offers */}
      {offers.length > 0 && (
        <div className="space-y-3">
          <h3 className="font-medium flex items-center gap-2">
            <Tag className="w-4 h-4 text-slate-400" /> Offers
          </h3>
          {offers.map((offer) => {
            const listing = item.listings.find((l) => l.id === offer.listing_id);
            return (
              <OfferCard
                key={offer.id}
                offer={offer}
                listingPrice={listing?.price}
                itemId={itemId}
              />
            );
          })}
        </div>
      )}

      {/* Messages */}
      {messages.length > 0 && (
        <div className="card space-y-3">
          <h3 className="font-medium flex items-center gap-2">
            <MessageSquare className="w-4 h-4 text-slate-400" /> Buyer messages
          </h3>
          <div className="space-y-3 max-h-80 overflow-y-auto">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex ${msg.direction === "outbound" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-xs rounded-xl px-4 py-2.5 text-sm ${
                    msg.direction === "outbound"
                      ? "bg-brand-600 text-white"
                      : "bg-slate-800 text-slate-200"
                  }`}
                >
                  {msg.direction === "inbound" && (
                    <p className="text-xs font-medium mb-1 text-slate-400">{msg.buyer_username}</p>
                  )}
                  <p>{msg.content}</p>
                  {msg.auto_replied && msg.direction === "outbound" && (
                    <p className="text-xs text-brand-300 mt-1">Auto-replied by agent</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
