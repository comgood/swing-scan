import { describe, expect, it } from "vitest";

import { mocks } from "@/mocks/handlers";

import { blockedStores, MemoryStorage, memoryStores } from "./memory-stores";
import {
  isOverTrialLimit,
  recordTrial,
  SESSION_KEY,
  TRIAL_KEY_PREFIX,
  TRIAL_WARNING_AT,
  type Trial,
} from "./trial-store";

const STRUCTURE = "a".repeat(64);
const trial = (structure: string, ...pairs: string[]): Trial => ({
  structure_key: structure,
  pair_keys: pairs,
});

describe("recordTrial (U-4, spec 0004)", () => {
  it("counts the first run as trial 1 of 1 this session", () => {
    expect(recordTrial(trial(STRUCTURE, "p1"), memoryStores())).toEqual({
      trialNumber: 1,
      sessionTotal: 1,
    });
  });

  it("adds runs that differ only in numbers to the same structure key (AC-1)", () => {
    const stores = memoryStores();
    recordTrial(trial(STRUCTURE, "lookback-252"), stores);
    expect(recordTrial(trial(STRUCTURE, "lookback-100"), stores)?.trialNumber).toBe(2);
  });

  it("does not add an identical pair again (AC-2)", () => {
    const stores = memoryStores();
    recordTrial(trial(STRUCTURE, "p1"), stores);
    expect(recordTrial(trial(STRUCTURE, "p1"), stores)).toEqual({
      trialNumber: 1,
      sessionTotal: 1,
    });
  });

  it("keeps a separate count per structure key, and one session total across all (AC-3)", () => {
    const stores = memoryStores();
    recordTrial(trial(STRUCTURE, "p1", "p2"), stores);
    expect(recordTrial(trial("b".repeat(64), "q1"), stores)).toEqual({
      trialNumber: 1,
      sessionTotal: 3,
    });
  });

  it("adds every new config pair of an exit lab run, skipping ones already seen", () => {
    const stores = memoryStores();
    // The portfolio mock's one pair is also the exit lab mock's first pair.
    recordTrial(mocks.backtestPortfolio.trial, stores);
    expect(recordTrial(mocks.backtestTradeLab.trial, stores)).toEqual({
      trialNumber: 5,
      sessionTotal: 5,
    });
  });

  it("counts a pair seen in an earlier session once toward this session, not again toward N", () => {
    const stores = memoryStores();
    recordTrial(trial(STRUCTURE, "p1", "p2"), stores);
    stores.session().clear(); // a new browser session; localStorage survives
    expect(recordTrial(trial(STRUCTURE, "p1"), stores)).toEqual({
      trialNumber: 2,
      sessionTotal: 1,
    });
  });

  it("stores seen pairs per structure key in localStorage and the session set in sessionStorage", () => {
    const stores = memoryStores();
    recordTrial(trial(STRUCTURE, "p1", "p2"), stores);
    expect(JSON.parse(stores.local().getItem(TRIAL_KEY_PREFIX + STRUCTURE) ?? "")).toEqual([
      "p1",
      "p2",
    ]);
    expect(JSON.parse(stores.session().getItem(SESSION_KEY) ?? "")).toEqual(["p1", "p2"]);
  });

  it("treats a corrupt stored value as empty and overwrites it", () => {
    const local = new MemoryStorage();
    local.setItem(TRIAL_KEY_PREFIX + STRUCTURE, "{not json");
    const session = new MemoryStorage();
    session.setItem(SESSION_KEY, JSON.stringify({ not: "a list" }));
    const stores = { local: () => local, session: () => session };
    expect(recordTrial(trial(STRUCTURE, "p1"), stores)).toEqual({
      trialNumber: 1,
      sessionTotal: 1,
    });
  });

  it.each(["local", "session", "both"] as const)(
    "returns null when %s storage is unavailable (AC-6)",
    (which) => {
      expect(recordTrial(trial(STRUCTURE, "p1"), blockedStores(which))).toBeNull();
    },
  );

  it("returns null when a write throws, as a full private mode quota does", () => {
    const full = new MemoryStorage();
    full.setItem = () => {
      throw new DOMException("Quota exceeded", "QuotaExceededError");
    };
    const stores = { local: () => full, session: () => new MemoryStorage() };
    expect(recordTrial(trial(STRUCTURE, "p1"), stores)).toBeNull();
  });

  it("uses the browser stores by default", () => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    expect(recordTrial(trial(STRUCTURE, "p1"))).toEqual({ trialNumber: 1, sessionTotal: 1 });
    expect(window.localStorage.getItem(TRIAL_KEY_PREFIX + STRUCTURE)).toBe('["p1"]');
    window.localStorage.clear();
    window.sessionStorage.clear();
  });
});

// Edges spec 0004 records under Consequences, locked so a change to them is deliberate.
describe("recordTrial edges (spec 0004 consequences)", () => {
  it("counts a pair repeated inside one response once (AC-2)", () => {
    expect(recordTrial(trial(STRUCTURE, "p1", "p1"), memoryStores())).toEqual({
      trialNumber: 1,
      sessionTotal: 1,
    });
  });

  it("records nothing for an empty pair list and shows trial 0 for a new structure", () => {
    const stores = memoryStores();
    expect(recordTrial(trial(STRUCTURE), stores)).toEqual({ trialNumber: 0, sessionTotal: 0 });
    expect(stores.local().length).toBe(0);
    expect(stores.session().length).toBe(0);
  });

  it("returns null when only the session write fails, keeping the pair in N (AC-6)", () => {
    const local = new MemoryStorage();
    const session = new MemoryStorage();
    session.setItem = () => {
      throw new DOMException("Quota exceeded", "QuotaExceededError");
    };
    const stores = { local: () => local, session: () => session };
    expect(recordTrial(trial(STRUCTURE, "p1"), stores)).toBeNull();
    expect(local.getItem(TRIAL_KEY_PREFIX + STRUCTURE)).toBe('["p1"]');
  });

  it("does not rewrite storage when a re run adds nothing (AC-2)", () => {
    const local = new MemoryStorage();
    const session = new MemoryStorage();
    const stores = { local: () => local, session: () => session };
    recordTrial(trial(STRUCTURE, "p1"), stores);
    let writes = 0;
    const counted = (storage: MemoryStorage) => {
      const original = storage.setItem.bind(storage);
      storage.setItem = (key, value) => {
        writes += 1;
        original(key, value);
      };
    };
    counted(local);
    counted(session);
    recordTrial(trial(STRUCTURE, "p1"), stores);
    expect(writes).toBe(0);
  });

  it("keeps a separate N per structure key while M sums them (AC-1, AC-3)", () => {
    const stores = memoryStores();
    recordTrial(trial(STRUCTURE, "p1", "p2", "p3"), stores);
    recordTrial(trial("b".repeat(64), "q1"), stores);
    expect(recordTrial(trial(STRUCTURE, "p4"), stores)).toEqual({
      trialNumber: 4,
      sessionTotal: 5,
    });
  });
});

describe("isOverTrialLimit (AC-5)", () => {
  it("warns from trial 10, not before", () => {
    expect(TRIAL_WARNING_AT).toBe(10);
    expect(isOverTrialLimit({ trialNumber: 9, sessionTotal: 40 })).toBe(false);
    expect(isOverTrialLimit({ trialNumber: 10, sessionTotal: 10 })).toBe(true);
    expect(isOverTrialLimit({ trialNumber: 11, sessionTotal: 11 })).toBe(true);
  });
});
