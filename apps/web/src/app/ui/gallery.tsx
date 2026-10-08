"use client";

// Every foundation part in every state that can be shown statically (spec 0003 AC-15).
// Each section is a labelled region so tests can run axe on it alone (AC-16).
import { useState, type ReactNode } from "react";

import { Banner } from "@/components/banner";
import { DataTable, type DataTableColumn } from "@/components/data-table";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { FormErrorSummary } from "@/components/form-error-summary";
import { FormRow } from "@/components/form-row";
import { NumberInput } from "@/components/number-input";
import { SignedValue } from "@/components/signed-value";
import { WarmupNotice } from "@/components/warmup-notice";
import { LIVE_TEXT, SYNTHETIC_TEXT } from "@/components/shell/data-mode-banner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Field, FieldDescription, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { errorAt, fieldErrorsFrom422 } from "@/lib/field-errors";
import { formatDate, formatInt, formatNumber, formatPct, formatPrice, formatR } from "@/lib/format";
import { Plus } from "lucide-react";

import { ProcedureNote, TrialCounter } from "@/features/honesty";

import { BacktestDemo } from "./backtest-demo";
import { HonestyDemo } from "./honesty-demo";
import { RuleBuilderStates } from "./rule-builder-states";

import {
  MANY_ROWS,
  SAMPLE_422,
  SAMPLE_ROWS,
  SAMPLE_TRIAL_STATES,
  WIDE_COLUMNS,
  WIDE_ROWS,
  type SampleRow,
  type WideRow,
} from "./sample";

export function GallerySection({
  id,
  title,
  children,
}: {
  id: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="flex min-w-0 flex-col gap-4">
      <h2 id={`${id}-title`} className="text-lg font-semibold">
        {title}
      </h2>
      {children}
    </section>
  );
}

const SAMPLE_COLUMNS: DataTableColumn<SampleRow>[] = [
  {
    accessorKey: "ticker",
    header: "Ticker",
    cell: (info) => <span className="font-mono">{info.getValue<string>()}</span>,
  },
  { accessorKey: "setup", header: "Setup" },
  {
    accessorKey: "return_pct",
    header: "Return",
    meta: { numeric: true, highlight: (row) => row.best },
    cell: (info) => <SignedValue value={info.getValue<number | null>()} format="pct" />,
  },
  {
    accessorKey: "win_rate_pct",
    header: "Win rate (%)",
    meta: { numeric: true },
    cell: (info) => formatNumber(info.getValue<number | null>(), { decimals: 1 }),
  },
  {
    accessorKey: "expectancy_r",
    header: "Expectancy",
    meta: { numeric: true },
    cell: (info) => <SignedValue value={info.getValue<number | null>()} format="r" />,
  },
  {
    accessorKey: "trades",
    header: "Trades",
    meta: { numeric: true },
    cell: (info) => formatInt(info.getValue<number>()),
  },
];

const WIDE_TABLE_COLUMNS: DataTableColumn<WideRow>[] = WIDE_COLUMNS.map((key) => ({
  accessorKey: key,
  header: key.replaceAll("_", " "),
  meta: { numeric: typeof WIDE_ROWS[0]?.[key] === "number" },
}));

const NO_ROWS: SampleRow[] = [];

export function Gallery() {
  const [lookback, setLookback] = useState<number | null>(20);
  const [stopPct, setStopPct] = useState<number | null>(8);
  const [cooldown, setCooldown] = useState<number | null>(999);
  const [warmupPending, setWarmupPending] = useState(false);
  const [busy, setBusy] = useState(false);
  const serverErrors = fieldErrorsFrom422(SAMPLE_422);

  return (
    <div className="flex min-w-0 flex-col gap-10">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold">UI gallery</h1>
        <p className="text-sm text-muted-foreground">
          Every foundation component in every state, with invented data (spec 0003), plus the
          research honesty guards (spec 0004) and the backtest report parts (spec 0007).
        </p>
      </header>

      <GallerySection id="buttons" title="Buttons">
        <div className="flex flex-wrap items-center gap-2">
          <Button>Run backtest</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="outline">Outline</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="destructive">Remove rule</Button>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm">Small</Button>
          <Button size="icon" aria-label="Add condition">
            <Plus aria-hidden="true" />
          </Button>
          <Button disabled>Disabled</Button>
          <Button loading>Loading</Button>
          <Button
            variant="outline"
            loading={busy}
            onClick={() => {
              setBusy(true);
              setTimeout(() => setBusy(false), 2000);
            }}
          >
            Click to load for 2 s
          </Button>
        </div>
      </GallerySection>

      <GallerySection id="form-controls" title="Form controls">
        <FormRow columns={3}>
          <Field>
            <FieldLabel>Name</FieldLabel>
            <Input placeholder="My breakout rule" />
            <FieldDescription>Shown in the results header.</FieldDescription>
          </Field>
          <Field invalid>
            <FieldLabel>Ticker</FieldLabel>
            <Input defaultValue="??" />
            <FieldError>Use letters only</FieldError>
          </Field>
          <Field disabled>
            <FieldLabel>Disabled</FieldLabel>
            <Input disabled defaultValue="Locked" />
          </Field>
        </FormRow>
        <FormRow columns={2}>
          <Field>
            <FieldLabel>Template</FieldLabel>
            <NativeSelect defaultValue="breakout">
              <NativeSelectOption value="breakout">Breakout</NativeSelectOption>
              <NativeSelectOption value="pullback">Pullback</NativeSelectOption>
            </NativeSelect>
          </Field>
          <Field orientation="horizontal">
            <Checkbox defaultChecked />
            <FieldLabel>Include delisted tickers in the backtest</FieldLabel>
          </Field>
        </FormRow>
      </GallerySection>

      <GallerySection id="number-input" title="Number input">
        <FormRow columns={3}>
          <NumberInput
            label="Lookback (bars)"
            integer
            min={2}
            max={260}
            value={lookback}
            onValueChange={setLookback}
          />
          <NumberInput
            label="Stop loss (%)"
            hint="Below the entry price"
            value={stopPct}
            onValueChange={setStopPct}
          />
          <NumberInput
            label="Cooldown (bars)"
            integer
            min={0}
            max={60}
            value={cooldown}
            onValueChange={setCooldown}
            error={errorAt(serverErrors, "lookback")}
          />
        </FormRow>
        <p className="text-xs text-muted-foreground">
          Current values: {String(lookback)}, {String(stopPct)}, {String(cooldown)}
        </p>
      </GallerySection>

      <GallerySection id="server-errors" title="Server errors (422)">
        <FormErrorSummary errors={serverErrors.form} />
      </GallerySection>

      <GallerySection id="formats" title="Numbers and badges">
        <dl className="grid grid-cols-1 gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
          {(
            [
              ["formatPct(3.254)", formatPct(3.254)],
              ["formatPct(-1.1)", formatPct(-1.1)],
              ["formatPct(0.001)", formatPct(0.001)],
              ["formatNumber(1234567.891)", formatNumber(1234567.891)],
              ["formatR(1.32)", formatR(1.32)],
              ["formatPrice(2310)", formatPrice(2310)],
              ["formatInt(1499.6)", formatInt(1499.6)],
              ["formatDate", formatDate("2024-01-22")],
              ["formatPct(null)", formatPct(null)],
            ] as const
          ).map(([name, text]) => (
            <div key={name} className="flex min-w-0 justify-between gap-4">
              <dt className="truncate font-mono text-xs text-muted-foreground">{name}</dt>
              <dd className="tabular-nums">{text}</dd>
            </div>
          ))}
        </dl>
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <SignedValue value={3.254} format="pct" />
          <SignedValue value={-1.1} format="pct" />
          <SignedValue value={0.001} format="pct" />
          <SignedValue value={0.41} format="r" />
          <SignedValue value={null} format="number" />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge>Default</Badge>
          <Badge variant="secondary">Secondary</Badge>
          <Badge variant="outline">Outline</Badge>
          <Badge variant="positive">+ Edge</Badge>
          <Badge variant="negative">- Edge</Badge>
          <Badge variant="warning">Live</Badge>
          <Badge variant="info">IS</Badge>
        </div>
      </GallerySection>

      <GallerySection id="data-table" title="Data table">
        <DataTable
          columns={SAMPLE_COLUMNS}
          data={SAMPLE_ROWS}
          getRowId={(row) => row.id}
          caption="Sample results, sorted by return"
          captionVisible
          initialSort={{ id: "return_pct", desc: true }}
        />
        <DataTable
          columns={SAMPLE_COLUMNS}
          data={MANY_ROWS}
          getRowId={(row) => row.id}
          caption="Paginated sample, 5 rows per page"
          captionVisible
          pageSize={5}
        />
        <DataTable
          columns={WIDE_TABLE_COLUMNS}
          data={WIDE_ROWS}
          getRowId={(row) => row.id}
          caption="Twelve column trade list"
          captionVisible
        />
        <DataTable
          columns={SAMPLE_COLUMNS}
          data={NO_ROWS}
          getRowId={(row) => row.id}
          caption="Empty table"
          captionVisible
          empty={<EmptyState title="No hits today" hint="Try another template or date." />}
        />
      </GallerySection>

      <GallerySection id="banners" title="Banners">
        <Banner variant="info">Results use the next bar&apos;s open for every fill.</Banner>
        <Banner variant="warning" title="Synthetic market">
          Prices are generated, not real. A long message wraps instead of widening the page:
          supercalifragilisticexpialidocious_long_identifier_without_spaces_0123456789.
        </Banner>
      </GallerySection>

      <GallerySection id="honesty" title="Research honesty guards">
        <p className="text-sm text-muted-foreground">
          Trial counter (U-4) in each state, then a live demo, the exit lab procedure note (U-8),
          and the data mode banners (U-1, U-2) that the page shell shows.
        </p>
        <div className="grid min-w-0 gap-4 md:grid-cols-2">
          {SAMPLE_TRIAL_STATES.map(({ label, state }, i) => (
            <div
              key={label}
              role="group"
              aria-labelledby={`trial-state-${i}`}
              className="flex min-w-0 flex-col gap-2 rounded-lg border p-4"
            >
              <h3 id={`trial-state-${i}`} className="text-sm font-medium">
                {label}
              </h3>
              <TrialCounter state={state} />
            </div>
          ))}
        </div>
        <div
          role="group"
          aria-labelledby="trial-demo"
          className="flex min-w-0 flex-col gap-2 rounded-lg border p-4"
        >
          <h3 id="trial-demo" className="text-sm font-medium">
            Live demo
          </h3>
          <HonestyDemo />
        </div>
        <div className="flex min-w-0 flex-col gap-2 rounded-lg border p-4">
          <h3 className="text-sm font-medium">Procedure note under the exit lab table</h3>
          <ProcedureNote />
        </div>
        <div className="flex min-w-0 flex-col gap-2">
          <h3 className="text-sm font-medium">Data mode banners</h3>
          <Banner variant="warning">{SYNTHETIC_TEXT}</Banner>
          <Banner variant="warning">{LIVE_TEXT}</Banner>
        </div>
      </GallerySection>

      <GallerySection id="backtest" title="Backtest report">
        <p className="text-sm text-muted-foreground">
          The assumptions header with its trial counter, IS beside OOS metrics, and the trade list
          in full and truncated, and the equity chart against the benchmark (spec 0007).
        </p>
        <BacktestDemo />
      </GallerySection>

      <GallerySection id="rule-builder" title="Rule builder">
        <p className="text-sm text-muted-foreground">
          Condition rows in each state (spec 0008): one row, both right side kinds, the 8 row limit,
          a 422 on its field, stale results, the bad link notice and the JSON panel.
        </p>
        <RuleBuilderStates />
      </GallerySection>

      <GallerySection id="loading" title="Loading">
        <div className="flex flex-col gap-2" aria-hidden="true">
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-4 w-1/2" />
        </div>
        <p className="flex items-center gap-2 text-sm">
          <Spinner /> Loading results…
        </p>
        <div className="flex flex-col items-start gap-2">
          <Button variant="outline" size="sm" onClick={() => setWarmupPending((p) => !p)}>
            {warmupPending ? "Stop the slow request" : "Start a slow request"}
          </Button>
          <WarmupNotice pending={warmupPending} />
        </div>
      </GallerySection>

      <GallerySection id="errors" title="Error states">
        <ErrorState error={{ kind: "network" }} onRetry={() => undefined} headingLevel={3} />
        <ErrorState error={{ kind: "timeout" }} onRetry={() => undefined} headingLevel={3} />
        <ErrorState
          error={{ kind: "http", status: 501, detail: "scan arrives with scope feature 8." }}
          onRetry={() => undefined}
          headingLevel={3}
        />
        <ErrorState
          error={{ kind: "http", status: 500 }}
          onRetry={() => undefined}
          headingLevel={3}
        />
      </GallerySection>

      <GallerySection id="empty-card" title="Empty state, card, separator">
        <EmptyState title="No trades yet" hint="Run a backtest to fill this table." />
        <Card>
          <CardHeader>
            <CardTitle>Assumptions</CardTitle>
            <CardDescription>Next open fills, 0.1% slippage, equal weight.</CardDescription>
          </CardHeader>
          <CardContent>
            <Separator />
            <p className="pt-3">Card body text.</p>
          </CardContent>
        </Card>
      </GallerySection>
    </div>
  );
}
