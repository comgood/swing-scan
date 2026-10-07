// In memory and blocked storage for the trial counter's tests and the /ui gallery (spec 0004).
import type { TrialStores } from "./trial-store";

export class MemoryStorage implements Storage {
  private items = new Map<string, string>();
  get length(): number {
    return this.items.size;
  }
  clear(): void {
    this.items.clear();
  }
  getItem(key: string): string | null {
    return this.items.get(key) ?? null;
  }
  key(index: number): string | null {
    return [...this.items.keys()][index] ?? null;
  }
  removeItem(key: string): void {
    this.items.delete(key);
  }
  setItem(key: string, value: string): void {
    this.items.set(key, String(value));
  }
}

/** Fresh, isolated local and session stores. */
export function memoryStores(): TrialStores {
  const local = new MemoryStorage();
  const session = new MemoryStorage();
  return { local: () => local, session: () => session };
}

/** Stores that throw like a browser with storage blocked. */
export function blockedStores(which: "local" | "session" | "both" = "both"): TrialStores {
  const ok = memoryStores();
  const blocked = (): Storage => {
    throw new DOMException("The operation is insecure.", "SecurityError");
  };
  return {
    local: which === "session" ? ok.local : blocked,
    session: which === "local" ? ok.session : blocked,
  };
}
