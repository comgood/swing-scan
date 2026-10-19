# 0013. Notice new data by polling meta, and let the result name the dataset that produced it

**Date**: 2026-10-18
**Status**: Accepted

## Summary

The site should notice by itself when the writer appends a trading day. It does that by asking the existing meta endpoint every 30 seconds while the tab is in front of you, and when the date moves it says so and offers a refresh rather than silently recomputing the numbers you are reading. To make the as of marker honest rather than approximately right, the backtest result now carries the dataset that produced it, which is a small contract change. There is no server push: holding a stream open on Lambda is billed for every second it stays open, which is a real cost for an event that happens once a day.

## Requirements

**User stories**:
- As someone reading the site, I want to know when the data I am looking at is no longer the latest, without reloading.
- As someone mid comparison, I do not want my numbers changing under me because a tick landed.
- As the owner, I want this to cost nothing and to keep working when the API is briefly unreachable.

**Acceptance criteria**:

- **AC-1**: An open page learns that the dataset changed within about 40 seconds of the writer publishing: up to 10 seconds for spec `0011`'s server side check floor plus up to 30 for the poll interval. No reload and no user action. (Measured from the writer, not from the API, which is why this is 40 and not 30.)
- **AC-2**: The as of date names the dataset that **actually produced** the displayed results, taken from the result itself and not inferred from a poll. A tick landing between request and response cannot make the marker wrong.
- **AC-3**: `Assumptions` gains `data_end` and `data_version`, echoed by every result that carries assumptions, so a result is self describing about its data. This goes through the project's `contract-change` process.
- **AC-4**: When a newer dataset is available, the view shows a notice saying so and telling the person to reload for the newer data. Existing scan, backtest and exit lab results stay exactly as they are.
- **AC-5**: Reloading the page clears the notice and shows results from the new dataset, with the as of marker matching. Nothing re-runs a backtest or an exit lab without a page load.
- **AC-6**: While the tab is not focused, no polling happens at all. On refocus the page checks once.
- **AC-7**: A failed or timed out poll changes nothing on screen, is not shown as an error, and the next poll recovers on its own.
- **AC-8**: When the API reports no dataset at all (`data` is `null`, which happens on a cold or empty store), the page shows no as of marker and no notice, and does not treat it as a change.
- **AC-9**: The data mode banner keeps its existing behaviour: static HTML holds the synthetic text and it switches only when health says exactly `live` (spec 0003, AC-4, U-1, U-2).
- **AC-10**: The trial counter keeps counting across a dataset change, and its warning names the dataset versions the trials were run against. Existing counts are not wiped: the dataset versions go in a **sibling key**, not inside the existing array, because `readSet` treats a non array value as empty and overwrites it (`trial-store.ts`). When a count spans two datasets the warning names **all** versions seen, oldest first, because the point of the counter is that you tried many variants and hiding that the data moved under them would defeat it.
- **AC-11**: Polling does not take over waking a cold API. The meta query does not fire until the health query has succeeded, so a cold start sees one request rather than two racing ones, and the existing health query keeps its job of waking the function.
- **AC-13**: The notice component is registered in the hidden `/ui` gallery with invented sample data, and passes that page's axe check (`apps/web/AGENTS.md`, the rule that every new shared component appears there).
- **AC-12**: Nothing here requires a streaming response, a held open connection, or a change to the function's invoke mode.

## Decision

**Chosen option**: Option 1: poll `/api/v1/meta` on a focused interval, and let the result name its own dataset.

A single TanStack Query with a 30 second `refetchInterval` that pauses when the tab loses focus, a small client context holding the dataset the displayed results came from, and a notice that leaves those results alone.

**Implementation skills**: `vercel-react-best-practices` (`vercel-labs/agent-skills`, `.claude/skills/vercel-react-best-practices/`) · `nextjs-app-router-patterns` (`wshobson/agents`, `.claude/skills/nextjs-app-router-patterns/`) · `shadcn` (`shadcn-ui/ui`, `.agents/skills/shadcn/`)

## Feature design

**The contract change** (AC-3, and why it is needed)

`Assumptions` describes itself as "Every setting that shaped the result, echoed so a run can be reproduced", and the dataset is the most load bearing thing it does not currently name. Without it the client has to guess which dataset computed a result, and the guess races a tick:

- `Assumptions` today carries `seed` and `oos_start` but no dataset identity.
- `ScanResponse.as_of` is the scan's as of date, which is not the same quantity as the dataset's last session.
- `data_version` alone is useless for this, because it reads `synthetic-2` for every tick.

So `Assumptions` gains two fields:

| Field | Type | Meaning |
|---|---|---|
| `data_end` | `IsoDate` | the last session in the dataset the result was computed on |
| `data_version` | `str` | the generator version of that dataset |

`PortfolioResult` already validates that its `oos_start` equals `assumptions.oos_start`, so this follows an established pattern. This is a `contract-change` PR: new fields on a frozen contract, the regenerated `packages/api-client`, updated mocks, and owner approval.

**Where the state lives**

There is no existing home for this, and the obvious candidates do not work: `Providers` holds only a `QueryClient`, `AppShell` is a server component, the scan's result is in the query cache keyed by rule alone, and the backtest and exit lab results are `useMutation` state inside their route. So:

| State | Where | Holds |
|---|---|---|
| the latest known dataset | the `meta` query's cache | `DataMeta | null` as last polled |
| the dataset the displayed results came from | **nowhere: it is read straight off the result** | `assumptions.data_end` on the backtest or exit lab result, `as_of` on the scan result, both already in hand wherever the result is rendered |

There is deliberately **no shared context and no pinned copy**. An earlier draft had a `DatasetContext` holding a pin plus the last request body, which existed only because the marker lived in the shell and had to reach across routes. Rendering the marker beside the results it describes removes the need: each route already holds its own result, the result now names its own dataset, and a value read at render time cannot go stale or outlive what it describes. The notice compares the polled `end` against that same local value.

**State transitions**

```
no dataset (data is null) ──> nothing shown at all, no notice                        (AC-8)

in sync ──poll end > result's data_end──> newer available ──refresh taken──> in sync
   ^                                            │
   └──────── page reloaded ────────┘

tab blurred: no polling (AC-6). On refocus, one check.
hard reload: results are in memory, so they clear. The scan's `?r=`
link re-runs on load, which re-pins from the fresh result.
```

**API surface**

No new endpoints. One contract change on an existing response.

| Endpoint | Method | Key inputs | Key outputs | Auth | Key errors |
|---|---|---|---|---|---|
| `/api/v1/meta` | GET | none | `contract_version`, `data` (`DataMeta | null`) | none | polled, so a failure is swallowed per AC-7 |
| `/api/v1/backtest` | POST | unchanged | `assumptions` now carries `data_end` and `data_version` | none | unchanged |

`oos_start` on the meta response is hardcoded `None` by the route and is not used by this feature.

**Value sourcing**

| Action | Value produced or displayed | Source |
|---|---|---|
| show the as of date | the date itself | `assumptions.data_end` from the displayed result (AC-2). For a scan, `ScanResponse.as_of`. Never the poll, which is what makes the marker honest |
| detect a change | what counts as changed | the polled `DataMeta.end` differing from the displayed result's `data_end`. A bare `data_version` comparison would not work, since it does not change per tick |
| the poll interval | 30 seconds | `META_POLL_MS = 30_000`, a named constant beside the query |
| pausing while blurred | the behaviour | TanStack Query v5 (`^5.104.1`): `refetchIntervalInBackground` defaults to false, so the interval does not fire. It follows **tab visibility**, not window focus, which matters for the test: a jsdom test needs the library's `focusManager` driven rather than a real blur event (AC-6) |
| checking once on refocus | the behaviour | `refetchOnWindowFocus`, on by default, which fires **only when the data is stale**. So `staleTime` must be finite and below the interval. Explicitly **not** modelled on `useHealth`, which sets `staleTime: Infinity` (`use-health.ts:34`) and would therefore never refetch on refocus at all |
| no dataset at all | what to render | `data` being `null` from the meta response, which `catalog.py` returns whenever no market is loaded. Nothing is rendered and no change is inferred (AC-8) |
| getting the newer data | a page reload | the notice tells the person to reload. No invalidation and no re-`mutate`, so no last request body is kept anywhere. The scan re-runs itself from its `?r=` link on load; a backtest is re-run by the person, which is right, since an exit lab run costs up to 25 seconds and nobody should spend that without asking (AC-5) |
| the notice's component | what renders it | a new component, not `Banner`. `banner.tsx` is text only and documented "Never closable", with `info` and `warning` for static page content and `danger` reserved for `role="alert"` on errors. A dynamic, dismissible notice carrying a button is none of those three, so it is built from `Alert` directly alongside `Banner` |
| the data mode banner's text | synthetic or live | unchanged, from `useHealth` and `isLive()` (AC-9) |
| the trial counter's dataset label | which dataset trials were counted on | `assumptions.data_end` from the result, appended to a **new sibling key** `swing-scan:trial-data:v1:<structure_key>` holding the set of dataset ends seen. The existing `swing-scan:trials:v1:<structure_key>` array is left exactly as it is, so no count is lost and `v1` does not become `v2` (AC-10) |
| the trial counter's recording call | where the dataset comes from | `recordTrial(trial, stores)` takes no dataset today, so the caller passes `assumptions.data_end` from the result it is already recording |
| waking a cold API | which request does it | the existing health query. The meta query is gated on `health.isSuccess` so it does not fire a second request at mount on a cold function (AC-11) |
| the notice's gallery entry | its sample data | invented data in the gallery's `sample.ts`, per `apps/web/AGENTS.md`'s rule for shared components (AC-13) |

**Key invariants**

- The as of marker is read from the result, never from the poll. A marker showing a dataset the results were not computed on is the exact dishonesty this feature exists to prevent.
- Nothing recomputes without the person asking. A poll may change a notice; it may never change a number.
- A poll failure is invisible. This is a background convenience, and an error surface for it would train people to ignore real errors.
- The data mode banner's logic is untouched. It is a research honesty surface governed by spec 0003 and U-1.
- A null dataset is not a change. It is the absence of data, and it renders nothing.

**Security model**

No authentication, no new surface, no new data. The meta endpoint is already public and returns only dataset metadata.

**Configuration required**

None. No new environment variable, no feature flag, no change to the function's invoke mode (AC-12).

**Critical test scenarios**

- Happy path: the polled `end` moves past the result's `data_end`, the notice appears, the results and the marker stay put, verifies **AC-1**, **AC-2**, **AC-4**.
- The race: a tick lands between the backtest request and its response, and the marker still names the dataset the result reports, verifies **AC-2**.
- Reload: after a reload the marker and the results both name the new dataset, and the notice is gone, verifies **AC-5**.
- Focus: a blurred tab issues no poll, and refocusing issues exactly one, verifies **AC-6**.
- Failure: a poll that 500s or times out leaves the page unchanged with no error surface, and the next poll succeeds, verifies **AC-7**.
- Empty: `data` is `null` and nothing is rendered, with no notice, verifies **AC-8**.
- Honesty: the banner still renders synthetic text in static HTML and switches only on exactly `live`, verifies **AC-9**.
- Trials: a dataset change does not reset the counter, and the warning names the dataset version, verifies **AC-10**.

## Build plan

Tracer Bullet. The thread is the backtest result naming its own dataset and the marker reading it, end to end, before the notice or the refresh exist.

1. The contract change: `Assumptions` gains `data_end` and `data_version`, the API populates them from the loaded market, satisfies **AC-3**
2. The `contract-change` PR: regenerated `packages/api-client`, updated mocks, owner approval, satisfies **AC-3**
3. The as of marker rendered beside each view's results, reading `assumptions.data_end` (or the scan's `as_of`) straight off the result, satisfies **AC-2**, **AC-5**
4. `useMeta`: one TanStack Query with `META_POLL_MS`, no background refetch, a finite `staleTime` below the interval so refocus checks once, gated on `health.isSuccess`, failures swallowed, `data: null` handled, satisfies **AC-1**, **AC-6**, **AC-7**, **AC-8**, **AC-11**
5. The notice component, built from `Alert` rather than `Banner`, plus its `/ui` gallery entry and sample data, satisfies **AC-4**, **AC-13**
6. The trial counter's sibling key holding the dataset ends seen, and the warning naming them, leaving the existing count arrays untouched, satisfies **AC-10**
7. Confirm the banner's behaviour is unchanged, satisfies **AC-9**
8. Watch it end to end against a real tick from spec `0012` on the local stack, satisfies **AC-1**, **AC-5**, **AC-12**

## Consequences

**Positive**:
- Honest by construction. The marker comes from the result, so it cannot name a dataset the numbers do not belong to, and the mid request race is closed rather than documented.
- Costs nothing: one small request per 30 focused seconds, none on a background tab, and no change to how the function is invoked or billed.
- Nothing is recomputed behind anyone's back, which matters most for the exit lab, where an unasked rerun would cost up to 25 seconds.
- Recovery needs no code: a dropped poll is a poll that failed, and the next works.
- `Assumptions` becomes genuinely self describing, which helps anything that ever stores or compares results, feature 23's run history included.

**Negative / tradeoffs**:
- It is a contract change, so the generated client, the mocks and owner approval are all in scope, and the feature grows from about a day to closer to two.
- Not push. Up to about 40 seconds can pass between the writer publishing and the page noticing, counting spec `0011`'s 10 second server check floor.
- A background tab learns nothing until you return to it.
- One piece of client state, the poll. The marker and the notice both read the result they sit next to, so there is nothing to keep in sync and no way to read the wrong one.
- A new notice component rather than reusing `Banner`, because `Banner`'s three variants all mean something this notice is not.
- The meta query cannot use `staleTime: Infinity` the way `useHealth` does, so the two shell queries now behave differently and someone will eventually wonder why.

**Neutral**:
- `oos_start` on the meta response stays hardcoded `None` and unused by this feature.
- The health query keeps waking a cold function; this feature does not take that over.
- If sub second push is ever genuinely needed, the notice and the marker stay and only the transport changes.

## Follow-up

- [ ] `useHealth` sets `staleTime: Infinity` and never refetches, so a mid session `data_mode` flip would leave the banner stale while the meta poll moves on. That is pre existing behaviour and out of scope here, but it is now visible because two shell queries sit side by side with different refresh rules, and someone will ask why.
- [ ] `ScanResponse.as_of` and `Assumptions.data_end` are related but not the same quantity. Worth confirming during step 1 that a scan's `as_of` equals the dataset's last session for a full history scan; if it does not, the scan needs `data_end` too.
- [ ] Feature 23 stores backtest runs. `Assumptions.data_end` is what lets a stored run say which data produced it, so that feature should rely on this rather than adding its own field.
- [ ] If the demo ever needs the data to move while someone watches, the cheap version is a tick on demand in the local stack rather than a faster poll. Worth considering with feature 18.
- [ ] Server sent events were rejected on cost, not feasibility. Revisit this spec rather than adding a second transport beside the poll.
- [ ] Check with feature 19's first real tick whether 30 seconds feels right. The constant is named and in one place so this is a one line change.

## Rationale

Reasoning, the options weighed, and the references: see [rationale.md](rationale.md).
