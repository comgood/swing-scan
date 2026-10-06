"use client";

import { useEffect, useState } from "react";

type Status =
  | { kind: "checking" }
  | { kind: "ok"; dataMode: string; version: string }
  | { kind: "error"; message: string };

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

// Scaffold check that the web app can reach the API (spec 0001, tracer bullet).
export function ApiStatus() {
  const [status, setStatus] = useState<Status>({ kind: "checking" });

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${API_URL}/api/v1/health`, { signal: controller.signal })
      .then(async (res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const body = (await res.json()) as { data_mode: string; version: string };
        setStatus({ kind: "ok", dataMode: body.data_mode, version: body.version });
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setStatus({ kind: "error", message: err instanceof Error ? err.message : String(err) });
      });
    return () => controller.abort();
  }, []);

  return (
    <p role="status" aria-live="polite" className="rounded-md border px-3 py-2 text-sm">
      {status.kind === "checking" && "Checking the API…"}
      {status.kind === "ok" &&
        `API reachable (data mode: ${status.dataMode}, version ${status.version}).`}
      {status.kind === "error" && `API not reachable: ${status.message}`}
    </p>
  );
}
