import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { TrendingUp, TrendingDown, Minus, Check, X, ArrowLeftRight } from "lucide-react";
import { offersApi } from "../lib/api";
import { StatusBadge } from "./StatusBadge";
import type { Offer } from "../types";

interface Props {
  offer: Offer;
  listingPrice?: number;
  itemId: number;
}

export function OfferCard({ offer, listingPrice, itemId }: Props) {
  const [counterAmount, setCounterAmount] = useState("");
  const [showCounter, setShowCounter] = useState(false);
  const qc = useQueryClient();

  const recommendation = (() => {
    try {
      return JSON.parse(offer.notes || "{}");
    } catch {
      return {};
    }
  })();

  const mutation = useMutation({
    mutationFn: (payload: { action: string; counter_amount?: number }) =>
      offersApi.decide(offer.id, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["offers", itemId] });
      qc.invalidateQueries({ queryKey: ["item", itemId] });
    },
  });

  const pct = listingPrice
    ? Math.round(((offer.amount - listingPrice) / listingPrice) * 100)
    : null;

  const isPending = offer.status === "pending";

  return (
    <div className="card space-y-3">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-slate-400">
            From <span className="text-slate-200 font-medium">{offer.buyer_username || "Anonymous"}</span>
          </p>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="text-2xl font-bold text-white">${offer.amount.toFixed(2)}</span>
            {listingPrice && (
              <span className="text-sm text-slate-400">
                vs ${listingPrice.toFixed(2)} asking
              </span>
            )}
            {pct !== null && (
              <span
                className={`flex items-center gap-0.5 text-xs font-medium ${
                  pct >= 0 ? "text-green-400" : "text-red-400"
                }`}
              >
                {pct >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                {pct > 0 ? "+" : ""}{pct}%
              </span>
            )}
          </div>
        </div>
        <StatusBadge status={offer.status} type="offer" />
      </div>

      {recommendation.recommendation && (
        <div className="bg-slate-800 rounded-lg p-3 text-sm">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-slate-400">AI recommendation:</span>
            <span
              className={`font-medium ${
                recommendation.recommendation === "accept"
                  ? "text-green-400"
                  : recommendation.recommendation === "decline"
                  ? "text-red-400"
                  : "text-yellow-400"
              }`}
            >
              {recommendation.recommendation.toUpperCase()}
              {recommendation.counter_price && ` at $${recommendation.counter_price}`}
            </span>
          </div>
          {recommendation.reasoning && (
            <p className="text-slate-400 text-xs">{recommendation.reasoning}</p>
          )}
        </div>
      )}

      {isPending && (
        <div className="space-y-2">
          {showCounter ? (
            <div className="flex gap-2">
              <input
                type="number"
                className="input"
                placeholder="Counter amount ($)"
                value={counterAmount}
                onChange={(e) => setCounterAmount(e.target.value)}
              />
              <button
                className="btn-primary whitespace-nowrap"
                disabled={!counterAmount || mutation.isPending}
                onClick={() =>
                  mutation.mutate({
                    action: "counter",
                    counter_amount: parseFloat(counterAmount),
                  })
                }
              >
                Send
              </button>
              <button className="btn-secondary" onClick={() => setShowCounter(false)}>
                Cancel
              </button>
            </div>
          ) : (
            <div className="flex gap-2 flex-wrap">
              <button
                className="btn-primary flex items-center gap-1.5"
                disabled={mutation.isPending}
                onClick={() => mutation.mutate({ action: "accept" })}
              >
                <Check className="w-4 h-4" /> Accept
              </button>
              <button
                className="btn-secondary flex items-center gap-1.5"
                disabled={mutation.isPending}
                onClick={() => setShowCounter(true)}
              >
                <ArrowLeftRight className="w-4 h-4" /> Counter
              </button>
              <button
                className="btn-danger flex items-center gap-1.5"
                disabled={mutation.isPending}
                onClick={() => mutation.mutate({ action: "decline" })}
              >
                <X className="w-4 h-4" /> Decline
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
