import type { Platform } from "../types";

const labels: Record<Platform, string> = {
  ebay: "eBay",
  vinted: "Vinted",
  depop: "Depop",
};

const colors: Record<Platform, string> = {
  ebay: "bg-yellow-500/20 text-yellow-300",
  vinted: "bg-teal-500/20 text-teal-300",
  depop: "bg-pink-500/20 text-pink-300",
};

export function PlatformBadge({ platform }: { platform: Platform }) {
  return (
    <span className={`badge ${colors[platform]}`}>{labels[platform]}</span>
  );
}
