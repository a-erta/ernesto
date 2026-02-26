import { useEffect, useRef, useState } from "react";

const BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000";
const WS_URL = BASE_URL.replace(/^http/, "ws");

export interface AgentEvent {
  type: string;
  step?: string;
  item_id?: number;
  data?: Record<string, unknown>;
  error?: string;
}

export function useItemWebSocket(itemId: number) {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [lastEvent, setLastEvent] = useState<AgentEvent | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const ws = new WebSocket(`${WS_URL}/ws/${itemId}`);
    wsRef.current = ws;

    ws.onmessage = (e) => {
      try {
        const event: AgentEvent = JSON.parse(e.data);
        setLastEvent(event);
        setEvents((prev) => [...prev.slice(-49), event]);
      } catch {}
    };

    ws.onerror = () => {};
    ws.onclose = () => {};

    return () => {
      ws.close();
    };
  }, [itemId]);

  return { events, lastEvent };
}
