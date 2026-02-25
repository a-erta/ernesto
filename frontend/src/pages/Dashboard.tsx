import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Plus, Package, Tag, TrendingUp, ShoppingBag } from "lucide-react";
import { itemsApi } from "../lib/api";
import { StatusBadge } from "../components/StatusBadge";
import { NewItemModal } from "../components/NewItemModal";
import type { Item } from "../types";

function StatCard({ label, value, icon: Icon, color }: {
  label: string; value: number; icon: React.ElementType; color: string;
}) {
  return (
    <div className="card flex items-center gap-4">
      <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${color}`}>
        <Icon className="w-5 h-5" />
      </div>
      <div>
        <p className="text-2xl font-bold">{value}</p>
        <p className="text-sm text-slate-400">{label}</p>
      </div>
    </div>
  );
}

function ItemRow({ item }: { item: Item }) {
  const images: string[] = (() => {
    try { return JSON.parse(item.image_paths || "[]"); } catch { return []; }
  })();
  const thumb = images[0];

  return (
    <Link
      to={`/items/${item.id}`}
      className="card flex items-center gap-4 hover:border-slate-600 transition-colors group"
    >
      <div className="w-14 h-14 rounded-lg bg-slate-800 overflow-hidden flex-shrink-0">
        {thumb ? (
          <img src={`/uploads/${thumb.split("/").pop()}`} alt="" className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-slate-600">
            <Package className="w-6 h-6" />
          </div>
        )}
      </div>

      <div className="flex-1 min-w-0">
        <p className="font-medium text-slate-100 truncate group-hover:text-white transition-colors">
          {item.title || item.user_description || "Untitled item"}
        </p>
        <p className="text-xs text-slate-500 mt-0.5">
          {item.category || "—"} · {item.brand || "—"}
        </p>
      </div>

      <div className="flex items-center gap-3 flex-shrink-0">
        {item.final_price || item.suggested_price ? (
          <span className="text-lg font-semibold text-green-400">
            ${(item.final_price ?? item.suggested_price)!.toFixed(2)}
          </span>
        ) : null}
        <StatusBadge status={item.status} />
      </div>
    </Link>
  );
}

export function Dashboard() {
  const [showModal, setShowModal] = useState(false);
  const { data: items = [], isLoading } = useQuery({
    queryKey: ["items"],
    queryFn: itemsApi.list,
    refetchInterval: 5000,
  });

  const stats = {
    total: items.length,
    listed: items.filter((i) => i.status === "listed").length,
    sold: items.filter((i) => i.status === "sold").length,
    revenue: items
      .filter((i) => i.status === "sold")
      .reduce((sum, i) => sum + (i.final_price ?? 0), 0),
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="text-slate-400 text-sm mt-0.5">Your selling pipeline</p>
        </div>
        <button
          className="btn-primary flex items-center gap-2"
          onClick={() => setShowModal(true)}
        >
          <Plus className="w-4 h-4" /> New Item
        </button>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Total items" value={stats.total} icon={Package} color="bg-slate-700 text-slate-300" />
        <StatCard label="Active listings" value={stats.listed} icon={Tag} color="bg-green-500/20 text-green-400" />
        <StatCard label="Items sold" value={stats.sold} icon={ShoppingBag} color="bg-emerald-500/20 text-emerald-400" />
        <StatCard label="Revenue ($)" value={Math.round(stats.revenue)} icon={TrendingUp} color="bg-brand-500/20 text-brand-400" />
      </div>

      <div>
        <h2 className="text-sm font-medium text-slate-400 mb-3">All items</h2>
        {isLoading ? (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="card h-20 animate-pulse bg-slate-800" />
            ))}
          </div>
        ) : items.length === 0 ? (
          <div className="card text-center py-16">
            <Package className="w-10 h-10 mx-auto text-slate-600 mb-3" />
            <p className="text-slate-400">No items yet.</p>
            <p className="text-slate-500 text-sm mt-1">
              Click <strong>New Item</strong> to start selling.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {items.map((item) => (
              <ItemRow key={item.id} item={item} />
            ))}
          </div>
        )}
      </div>

      {showModal && <NewItemModal onClose={() => setShowModal(false)} />}
    </div>
  );
}
