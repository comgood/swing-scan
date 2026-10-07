"use client";

// A live trial counter for the /ui gallery (spec 0004 AC-9): each click records a numbers only
// tweak of one invented rule, so you can watch N climb to the warning at 10. It uses in memory
// storage, so the gallery never touches your real counts.
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { RunTrialCounter } from "@/features/honesty";
import { memoryStores } from "@/features/honesty/memory-stores";

import { SAMPLE_STRUCTURE_KEY } from "./sample";

function Demo({ onReset }: { onReset: () => void }) {
  const [stores] = useState(memoryStores);
  const [tweak, setTweak] = useState(1);
  const trial = { structure_key: SAMPLE_STRUCTURE_KEY, pair_keys: [`gallery-tweak-${tweak}`] };
  return (
    <div className="flex min-w-0 flex-col gap-3">
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" size="sm" onClick={() => setTweak((t) => t + 1)}>
          Run a numbers only tweak
        </Button>
        <Button variant="ghost" size="sm" onClick={onReset}>
          Reset the demo
        </Button>
      </div>
      <RunTrialCounter trial={trial} stores={stores} />
    </div>
  );
}

export function HonestyDemo() {
  const [run, setRun] = useState(0);
  return <Demo key={run} onReset={() => setRun((r) => r + 1)} />;
}
