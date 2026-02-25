import { clsx } from "clsx";
import {
  Camera,
  FileText,
  Upload,
  MessageSquare,
  CheckCircle,
  XCircle,
  Loader2,
} from "lucide-react";
import type { ItemStatus } from "../types";

const STEPS = [
  { key: "analyzing", label: "Analysing photos", icon: Camera },
  { key: "ready", label: "Listing generated", icon: FileText },
  { key: "publishing", label: "Publishing", icon: Upload },
  { key: "listed", label: "Listed & managing", icon: MessageSquare },
  { key: "sold", label: "Sold", icon: CheckCircle },
];

const STATUS_ORDER: Record<ItemStatus, number> = {
  draft: 0,
  analyzing: 1,
  ready: 2,
  publishing: 3,
  listed: 4,
  sold: 5,
  archived: -1,
};

interface Props {
  status: ItemStatus;
  currentStep?: string;
}

export function AgentTimeline({ status, currentStep }: Props) {
  const currentIdx = STATUS_ORDER[status] ?? 0;

  return (
    <div className="flex items-center gap-2 flex-wrap">
      {STEPS.map((step, idx) => {
        const done = idx < currentIdx;
        const active = idx === currentIdx;
        const Icon = step.icon;

        return (
          <div key={step.key} className="flex items-center gap-2">
            <div
              className={clsx(
                "flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all",
                done && "bg-green-500/20 text-green-300",
                active && "bg-brand-500/20 text-brand-300 ring-1 ring-brand-500",
                !done && !active && "bg-slate-800 text-slate-500"
              )}
            >
              {active && status !== "sold" ? (
                <Loader2 className="w-3 h-3 animate-spin" />
              ) : done ? (
                <CheckCircle className="w-3 h-3" />
              ) : (
                <Icon className="w-3 h-3" />
              )}
              {step.label}
            </div>
            {idx < STEPS.length - 1 && (
              <div className={clsx("w-4 h-px", done ? "bg-green-500/40" : "bg-slate-700")} />
            )}
          </div>
        );
      })}
      {status === "archived" && (
        <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-slate-700 text-slate-400">
          <XCircle className="w-3 h-3" /> Archived
        </span>
      )}
    </div>
  );
}
