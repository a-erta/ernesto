import { Routes, Route } from "react-router-dom";
import { Tag, Github } from "lucide-react";
import { Dashboard } from "./pages/Dashboard";
import { ItemDetail } from "./pages/ItemDetail";

function Layout({ children }: { children: React.ReactNode }) {
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
          <a
            href="https://github.com"
            target="_blank"
            rel="noreferrer"
            className="text-slate-500 hover:text-slate-300 transition-colors"
          >
            <Github className="w-5 h-5" />
          </a>
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

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/items/:id" element={<ItemDetail />} />
      </Routes>
    </Layout>
  );
}
