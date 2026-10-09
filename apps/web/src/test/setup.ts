// DOM setup for component tests (spec 0003 AC-16): jest-dom matchers, cleanup, and stubs for
// what Base UI needs and jsdom lacks. Lightweight Charts needs a canvas, so every test gets the
// recording fake in `lightweight-charts-fake.ts` instead.
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

import { charts } from "./lightweight-charts-fake";

vi.mock("lightweight-charts", () => import("./lightweight-charts-fake"));

afterEach(() => {
  cleanup();
  charts.length = 0;
});

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver;

if (typeof window !== "undefined") {
  window.matchMedia ??= (query: string) =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addListener() {},
      removeListener() {},
      addEventListener() {},
      removeEventListener() {},
      dispatchEvent: () => false,
    }) as MediaQueryList;

  if (typeof window.PointerEvent === "undefined") {
    class PointerEventStub extends MouseEvent {
      readonly pointerId: number;
      readonly pointerType: string;
      constructor(type: string, init: PointerEventInit = {}) {
        super(type, init);
        this.pointerId = init.pointerId ?? 1;
        this.pointerType = init.pointerType ?? "mouse";
      }
    }
    window.PointerEvent = PointerEventStub as unknown as typeof PointerEvent;
  }

  Element.prototype.scrollIntoView ??= function scrollIntoView() {};
}
