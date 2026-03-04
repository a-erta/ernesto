import { useState, useEffect, useCallback } from "react";
import { checkBackendHealth } from "../lib/api";

export type BackendStatus = "checking" | "connected" | "error";

const POLL_MS = 60_000;
const RETRY_MS = 10_000;

export function useBackendHealth() {
  const [status, setStatus] = useState<BackendStatus>("checking");
  const [message, setMessage] = useState<string | null>(null);

  const run = useCallback(async () => {
    setStatus("checking");
    setMessage(null);
    const result = await checkBackendHealth();
    if (result.ok) {
      setStatus("connected");
      setMessage(null);
    } else {
      setStatus("error");
      setMessage(result.message ?? "Backend unavailable");
    }
  }, []);

  useEffect(() => {
    run();
    const interval = setInterval(run, POLL_MS);
    return () => clearInterval(interval);
  }, [run]);

  // Retry soon after error so transient failures recover
  useEffect(() => {
    if (status !== "error") return;
    const t = setTimeout(run, RETRY_MS);
    return () => clearTimeout(t);
  }, [status, run]);

  return { status, message, retry: run };
}
