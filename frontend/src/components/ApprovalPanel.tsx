import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle, XCircle, TrendingUp, ExternalLink, FileText } from "lucide-react";
import { itemsApi } from "../lib/api";
import type { Item } from "../types";

interface Props {
  item: Item;
}

export function ApprovalPanel({ item }: Props) {
  const [finalPrice, setFinalPrice] = useState(
    item.suggested_price?.toFixed(2) ?? ""
  );
  const [description, setDescription] = useState(
    item.proposed_description ?? ""
  );
  const qc = useQueryClient();

  const analysis = (() => {
    try {
      return JSON.parse(item.ai_analysis || "{}");
    } catch {
      return {};
    }
  })();

  const approveMutation = useMutation({
    mutationFn: () =>
      itemsApi.approve(item.id, parseFloat(finalPrice), description),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["item", item.id] }),
  });

  const cancelMutation = useMutation({
    mutationFn: () => itemsApi.cancel(item.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["item", item.id] }),
  });

  return (
    <div className="card border-brand-500/40 bg-brand-900/10 space-y-4">
      <div className="flex items-center gap-2">
        <div className="w-2 h-2 rounded-full bg-brand-400 animate-pulse" />
        <h3 className="font-semibold text-brand-300">Awaiting your approval</h3>
      </div>

      <p className="text-sm text-slate-400">
        Review the AI-generated listing below. Edit the description and price as needed, then approve to publish.
      </p>

      {/* AI Analysis summary */}
      <div className="grid grid-cols-2 gap-3 text-sm">
        {[
          ["Category", analysis.category],
          ["Brand", analysis.brand],
          ["Condition", analysis.condition],
          ["Color", analysis.color],
          ["Size", analysis.size],
          ["Confidence", analysis.confidence ? `${Math.round(analysis.confidence * 100)}%` : null],
        ]
          .filter(([, v]) => v)
          .map(([label, value]) => (
            <div key={label as string} className="bg-slate-800 rounded-lg p-2.5">
              <p className="text-slate-500 text-xs">{label}</p>
              <p className="text-slate-200 font-medium mt-0.5">{value}</p>
            </div>
          ))}
      </div>

      {/* Description */}
      <div>
        <label className="block text-sm font-medium text-slate-300 mb-1.5 flex items-center gap-1.5">
          <FileText className="w-3.5 h-3.5 text-brand-400" />
          Listing description
          <span className="text-xs text-slate-500 font-normal ml-1">(AI-generated — edit freely)</span>
        </label>
        <textarea
          className="input w-full resize-y min-h-[120px] font-normal text-sm leading-relaxed"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Describe your item for potential buyers…"
          rows={5}
        />
        <p className="text-xs text-slate-500 mt-1">
          {description.length} characters · This description will be used across all selected platforms.
        </p>
      </div>

      {/* Comparables */}
      {item.comparables.length > 0 && (
        <div>
          <p className="text-xs font-medium text-slate-400 mb-2 flex items-center gap-1">
            <TrendingUp className="w-3 h-3" /> Comparable sold listings
          </p>
          <div className="space-y-1.5 max-h-40 overflow-y-auto">
            {item.comparables.map((c) => (
              <div
                key={c.id}
                className="flex items-center justify-between text-xs bg-slate-800 rounded-lg px-3 py-2"
              >
                <span className="text-slate-300 truncate flex-1 mr-2">{c.title}</span>
                <span className="text-green-400 font-medium whitespace-nowrap">
                  €{c.sold_price.toFixed(2)}
                </span>
                {c.url && (
                  <a
                    href={c.url}
                    target="_blank"
                    rel="noreferrer"
                    className="ml-2 text-slate-500 hover:text-slate-300"
                  >
                    <ExternalLink className="w-3 h-3" />
                  </a>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Price */}
      <div>
        <label className="block text-sm font-medium text-slate-300 mb-1.5">
          Final asking price (€)
        </label>
        <div className="flex gap-2">
          <input
            type="number"
            className="input"
            value={finalPrice}
            onChange={(e) => setFinalPrice(e.target.value)}
            step="0.01"
            min="0"
          />
          {item.suggested_price && (
            <button
              className="btn-secondary whitespace-nowrap text-xs"
              onClick={() => setFinalPrice(item.suggested_price!.toFixed(2))}
            >
              Use €{item.suggested_price.toFixed(2)}
            </button>
          )}
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-3">
        <button
          className="btn-primary flex-1 flex items-center justify-center gap-2"
          disabled={!finalPrice || approveMutation.isPending}
          onClick={() => approveMutation.mutate()}
        >
          <CheckCircle className="w-4 h-4" />
          {approveMutation.isPending ? "Publishing..." : "Approve & Publish"}
        </button>
        <button
          className="btn-danger flex items-center gap-2"
          disabled={cancelMutation.isPending}
          onClick={() => cancelMutation.mutate()}
        >
          <XCircle className="w-4 h-4" /> Cancel
        </button>
      </div>
    </div>
  );
}
