import { useEffect, useRef, useCallback } from "react";
import type { AgentEvent } from "../types";

export function useItemSocket(
  itemId: number | null,
  onEvent: (event: AgentEvent) => void
) {
  const wsRef = useRef<WebSocket | null>(null);
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  const connect = useCallback(() => {
    if (!itemId) return;
    const apiUrl = import.meta.env.VITE_API_URL;
    const origin = apiUrl ? new URL(apiUrl).origin : window.location.origin;
    const protocol = origin.startsWith("https") ? "wss" : "ws";
    const host = apiUrl ? new URL(apiUrl).host : window.location.host;
    const ws = new WebSocket(`${protocol}://${host}/ws/${itemId}`);

    ws.onmessage = (e) => {
      try {
        const event: AgentEvent = JSON.parse(e.data);
        onEventRef.current(event);
      } catch {
        // ignore malformed frames
      }
    };

    ws.onclose = () => {
      // Reconnect after 3s if still mounted
      setTimeout(() => {
        if (wsRef.current === ws) connect();
      }, 3000);
    };

    // Keepalive ping every 20s
    const ping = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.send("ping");
    }, 20_000);

    ws.onopen = () => {};
    wsRef.current = ws;

    return () => {
      clearInterval(ping);
      ws.close();
    };
  }, [itemId]);

  useEffect(() => {
    const cleanup = connect();
    return () => {
      cleanup?.();
      wsRef.current = null;
    };
  }, [connect]);
}
