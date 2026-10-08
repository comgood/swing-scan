// The portfolio backtest report (spec 0007 decision 11). Static: the inputs are read from the URL
// in the browser, inside Suspense, as a static export requires for `useSearchParams`.
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { BacktestRoute } from "@/features/backtest";

export default function BacktestPage() {
  return (
    <Suspense fallback={<Skeleton className="h-40 w-full" />}>
      <BacktestRoute />
    </Suspense>
  );
}
