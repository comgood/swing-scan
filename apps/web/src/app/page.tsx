import { ApiStatus } from "./api-status";

export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-4 py-16">
      <h1 className="text-3xl font-semibold">Swing Scan</h1>
      <p className="text-base">
        Build swing trading entry rules, backtest them honestly, and compare exits on identical
        entries.
      </p>
      <ApiStatus />
      <p className="text-sm opacity-80">
        Portfolio project running on a generated market. Not investment advice.
      </p>
    </main>
  );
}
