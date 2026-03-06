import { useState, useEffect } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { Tag, Github, LogOut, Link2 } from "lucide-react";
import { Dashboard } from "./pages/Dashboard";
import { ItemDetail } from "./pages/ItemDetail";
import { Login } from "./pages/Login";
import { useAuth } from "./context/AuthContext";
import { isSupabaseConfigured } from "./lib/supabase";
import { getBackendOrigin } from "./lib/api";
import { BackendStatus } from "./components/BackendStatus";
import { api } from "./lib/api";

/** When we load with ?ebay_connected=1 after OAuth callback, close popup and notify opener. */
function useEbayCallbackHandler() {
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("ebay_connected") !== "1") return;
    if (window.opener) {
      window.opener.postMessage({ type: "ebay_connected" }, window.location.origin);
      window.close();
    } else {
      window.history.replaceState({}, "", window.location.pathname || "/");
    }
  }, []);
}

function ConnectEbayButton() {
  const { session } = useAuth();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);

  const handleConnect = async () => {
    setError(null);
    setConnected(false);
    if (!isSupabaseConfigured) {
      const origin = encodeURIComponent(window.location.origin);
      window.open(`${getBackendOrigin()}/api/auth/ebay/authorize?redirect_origin=${origin}`, "ebay_oauth", "width=600,height=700,scrollbars=yes");
      return;
    }
    if (!session?.access_token) {
      setError("Please log in to connect eBay");
      return;
    }
    setLoading(true);
    try {
      const { data } = await api.get<{ url: string }>("/auth/ebay/authorize", {
        headers: { Accept: "application/json" },
        params: { redirect_origin: window.location.origin },
      });
      if (data?.url) {
        const popup = window.open(data.url, "ebay_oauth", "width=600,height=700,scrollbars=yes");
        if (popup) {
          const t = setInterval(() => {
            if (popup.closed) {
              clearInterval(t);
              setLoading(false);
            }
          }, 300);
          return;
        }
        window.location.href = data.url;
      } else {
        setError("Could not get eBay authorization URL");
      }
    } catch (e: unknown) {
      const msg = e && typeof e === "object" && "response" in e
        ? (e as { response?: { data?: { detail?: string } } }).response?.data?.detail
        : null;
      setError(msg || "Failed to start eBay connection");
    }
    setLoading(false);
  };

  useEffect(() => {
    const onMessage = (e: MessageEvent) => {
      if (e.data?.type === "ebay_connected") {
        setConnected(true);
        setError(null);
        setLoading(false);
      }
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, []);

  return (
    <button
      type="button"
      onClick={handleConnect}
      disabled={loading}
      className="text-slate-500 hover:text-amber-400 transition-colors flex items-center gap-1.5 text-sm disabled:opacity-50"
      title={error || "Connect your eBay account (OAuth)"}
    >
      <Link2 className="w-4 h-4 shrink-0" />
      <span className="hidden sm:inline">
        {loading ? "Connecting…" : connected ? "eBay connected" : "Connect eBay"}
      </span>
      {error && <span className="text-amber-400 text-xs">({error})</span>}
      {connected && !error && <span className="text-emerald-500 text-xs">✓</span>}
    </button>
  );
}

function Layout({ children }: { children: React.ReactNode }) {
  const { user, signOut } = useAuth();

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-slate-800 bg-slate-950/80 backdrop-blur-sm sticky top-0 z-40">
        <div className="max-w-5xl mx-auto px-4 h-14 flex items-center justify-between">
          <a href="/" className="flex items-center gap-2.5 font-bold text-lg">
            <div className="w-7 h-7 bg-brand-600 rounded-lg flex items-center justify-center">
              <Tag className="w-4 h-4 text-white" />
            </div>
            <span>Ernesto</span>
            <span className="text-xs font-normal text-slate-500 ml-1">v0.1</span>
          </a>
          <div className="flex items-center gap-3">
            <BackendStatus />
            <ConnectEbayButton />
            {user && (
              <span className="text-xs text-slate-500 hidden sm:block truncate max-w-[160px]">
                {user.email}
              </span>
            )}
            <a
              href="https://github.com"
              target="_blank"
              rel="noreferrer"
              className="text-slate-500 hover:text-slate-300 transition-colors"
            >
              <Github className="w-5 h-5" />
            </a>
            {isSupabaseConfigured && user && (
              <button
                onClick={signOut}
                title="Sign out"
                className="text-slate-500 hover:text-slate-300 transition-colors"
              >
                <LogOut className="w-5 h-5" />
              </button>
            )}
          </div>
        </div>
      </header>

      <main className="flex-1 max-w-5xl mx-auto w-full px-4 py-8">
        {children}
      </main>

      <footer className="border-t border-slate-800 py-4 text-center text-xs text-slate-600">
        Ernesto — Agentic selling assistant
      </footer>
    </div>
  );
}

function ProtectedRoutes() {
  const { session, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-950">
        <div className="w-6 h-6 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  // If Supabase is not configured (local dev), skip auth gate entirely
  if (!isSupabaseConfigured || session) {
    return (
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/items/:id" element={<ItemDetail />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Layout>
    );
  }

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}

export default function App() {
  useEbayCallbackHandler();
  return <ProtectedRoutes />;
}
