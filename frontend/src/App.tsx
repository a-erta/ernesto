import { Routes, Route, Navigate } from "react-router-dom";
import { Tag, Github, LogOut } from "lucide-react";
import { Dashboard } from "./pages/Dashboard";
import { ItemDetail } from "./pages/ItemDetail";
import { Login } from "./pages/Login";
import { useAuth } from "./context/AuthContext";
import { isSupabaseConfigured } from "./lib/supabase";

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
  return <ProtectedRoutes />;
}
