import { Wifi, WifiOff, Loader2 } from "lucide-react";
import { useBackendHealth } from "../hooks/useBackendHealth";
import { getBackendOrigin } from "../lib/api";

export function BackendStatus() {
  const { status, message, retry } = useBackendHealth();
  const origin = getBackendOrigin();

  if (status === "checking") {
    return (
      <span
        className="flex items-center gap-1.5 text-slate-500 text-xs"
        title="Checking backend…"
      >
        <Loader2 className="w-3.5 h-3.5 animate-spin shrink-0" />
        <span className="hidden sm:inline">Backend…</span>
      </span>
    );
  }

  if (status === "connected") {
    return (
      <span
        className="flex items-center gap-1.5 text-emerald-500/90 text-xs"
        title={`Backend connected (${origin})`}
      >
        <span className="relative flex h-2 w-2 shrink-0">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
        </span>
        <span className="hidden sm:inline">Connected</span>
      </span>
    );
  }

  return (
    <div className="flex items-center gap-1.5 text-amber-400/90 text-xs">
      <WifiOff className="w-3.5 h-3.5 shrink-0" />
      <span className="hidden sm:inline max-w-[140px] truncate" title={message ?? undefined}>
        {message ?? "Disconnected"}
      </span>
      <button
        type="button"
        onClick={retry}
        className="rounded px-1.5 py-0.5 text-slate-400 hover:bg-slate-800 hover:text-slate-200 transition-colors"
        title="Retry connection"
      >
        Retry
      </button>
    </div>
  );
}
