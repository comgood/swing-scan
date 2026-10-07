"use client";

// Shows whether the API answered the shell's health ping (spec 0003 AC-4).
import { useHealth } from "./use-health";

export function ApiStatus() {
  const health = useHealth();

  let text = "Checking the API…";
  if (health.isSuccess) {
    text = `API ready (data: ${health.data.data_mode ?? "n/a"}, version ${health.data.version ?? "n/a"})`;
  } else if (health.isError) {
    text = "API not reachable";
  }

  return (
    <p role="status" className="min-w-0 text-xs break-words text-muted-foreground">
      {text}
    </p>
  );
}
