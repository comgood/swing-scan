# 0013. Rationale: live refresh and push

Reasoning, options and references for [index.md](index.md).

## Context

> ⚠️ Premise note: the scope asks for "the server pushing the change rather than the browser asking again and again", and names holding a stream open as a constraint that "reaches past the UI". It does reach past the UI, and the answer it reaches is that this project should not push. The API runs in a Lambda behind a Function URL, and Lambda bills for wall clock duration, so a held open stream is billed for every second any viewer has the page open, whether or not anything is happening. The event being pushed happens once a day. Paying continuously to deliver a daily event, on a project whose stated constraint is $0 a month, is the wrong trade. The scope already anticipates the alternative in its own done when, which allows the hosted demo to "fall back to asking on a timer"; this spec makes that the primary rather than the fallback, and there is no second transport.

Spec `0011` gave the API a change check and a background reload, so the server already serves a new dataset within seconds of the writer publishing one. Spec `0012` provides something to notice. What is missing is the page noticing: today the as of date is rendered once and never moves, and `useHealth` is deliberately `staleTime: Infinity`, so nothing on the client ever asks again.

The forces at play:

- **Cost model of the host.** Lambda duration billing is the whole argument. Anything that holds a connection converts an idle viewer into a running function.
- **The 15 minute function limit.** Even if duration were free, a stream cannot outlive the invocation, so a client reconnect loop is required regardless. Push here is not push, it is polling with extra steps and a longer timer.
- **Change frequency.** One append per day. Any interval under a minute is already far tighter than the signal.
- **An honesty surface, not a convenience surface.** The as of date and the data mode banner are governed by U-1, U-2 and spec 0003. A refresh mechanism that let the marker and the numbers disagree would damage the thing the project is actually about.
- **The exit lab's cost.** A warm six config run is budgeted at 25 seconds (X-7). Recomputing it unasked because a tick landed would be both slow and rude.
- **What already exists.** TanStack Query is in the stack, `/api/v1/meta` already returns the dataset's `end` and `data_version`, and `useHealth` is a working model for a single shell query. Almost nothing needs inventing.

## Options considered

### Option 1: poll the meta endpoint on a focused interval (chosen)

One query against `/api/v1/meta` every 30 seconds while the tab has focus, comparing the returned `end` and `data_version` against the dataset the displayed results were computed on.

**Pros**:
- A few lines against an endpoint and a library already in place.
- Costs one small request per 30 focused seconds and literally nothing on a background tab.
- No change to the function's invoke mode, no streaming, no reconnect logic, and failure recovery is free.
- Within about 40 seconds of the writer, counting `0011`'s server side floor, which is far inside what a daily event needs.

**Cons**:
- Not push, so the scope's wording is not satisfied literally.
- Up to about 40 seconds of lag, and a background tab learns nothing until refocused.

### Option 2: server sent events over a streaming Function URL

Put the function in response streaming mode, hold an SSE connection per viewer, and emit an event when the dataset changes.

**Pros**:
- Genuine push, sub second, and the more impressive thing to demonstrate.
- One mechanism, no interval to tune.

**Cons**:
- Billed for the entire time every viewer's stream is open. On a page someone leaves open, that is a function running continuously, which breaks the $0 constraint in the one scenario most likely to happen.
- Capped by the 15 minute invocation limit, so the client needs reconnect logic anyway and the connection is not actually durable.
- Requires the Lambda Web Adapter configured for response streaming and the function switched to a streaming invoke mode, which is real infrastructure change for a daily event.
- The server would need a way to know the dataset changed in order to emit, which is the same check `0011` already does per request, so the detection work is not even saved.

### Option 3: both, streaming locally and polling when deployed

Build SSE for the local stack where duration is free, and poll on the hosted demo.

**Pros**:
- The streaming code exists and can be shown, with no hosted cost.

**Cons**:
- Two transports to write, test and keep honest, where one of them is never exercised by anyone except the author.
- The hosted demo, the thing anyone actually looks at, runs the path that got less attention.
- Doubles the surface for the one bug that matters here, a marker disagreeing with its numbers.

### Option 4: refetch everything automatically on change

Poll as in option 1, but re-run the scan, backtest and exit lab queries as soon as a change is seen.

**Pros**:
- Simpler state: there is only ever one dataset in play, so no pinning and no comparison to get wrong.
- The page is always current with no action needed.

**Cons**:
- Changes numbers under someone's eyes mid read, which for a research tool is the worst moment to do it.
- Spends up to 25 seconds of exit lab compute unasked, every tick, for every open page.
- Removes the person's ability to finish what they were comparing.

## Rationale

The cost model of the host decides this. Lambda bills duration, the event is daily, and a stream converts every idle open tab into a running function, so option 2 spends continuously to deliver something that happens once a day and still needs reconnect logic because of the 15 minute cap. Option 3 keeps that cost off the bill but puts the less exercised path in front of the only audience there is. Option 1 reaches the page within about 40 seconds of the writer, using a library and an endpoint that are already there, with recovery that needs no code because a failed poll is just a poll that failed.

Between option 1 and option 4, the deciding force is that the as of date is an honesty surface rather than a status indicator. Tying the marker to the dataset the results actually came from is what lets it always name the right one (AC-2) and lets the notice be an offer rather than an interruption (AC-4). It costs bookkeeping, three pieces of client state instead of one, and buys the property the project cares most about. Recomputing automatically would be simpler state and worse behaviour, and it would spend the exit lab's 25 second budget without being asked.

**The contract change was not in the first draft of this spec, and it should have been.** That draft had the client pin "the latest meta at the moment results arrive", which reads reasonable and is wrong: a tick landing between the request and the response leaves the marker naming a dataset the result was not computed on, which is precisely the failure the feature exists to prevent. Nothing in the existing responses closes that gap, because `Assumptions` carries no dataset identity, `ScanResponse.as_of` is the scan's as of date rather than the dataset's last session, and `data_version` reads the same for every tick. The only honest fix is for the server to say which data produced a result, so `Assumptions` gains `data_end` and `data_version`. That is a correction to an incomplete contract as much as an addition: `Assumptions` describes itself as "Every setting that shaped the result, echoed so a run can be reproduced", and a result cannot be reproduced without knowing its data. The cost is a `contract-change` PR and a feature closer to two days than one, which the engineer accepted knowing the alternative was an honesty surface with an asterisk.

Three smaller corrections came from the same review and are worth recording because each was a confident claim that the code contradicted. There is **no existing home for client state spanning both routes**, since `Providers` holds only a `QueryClient`, `AppShell` is a server component, and the backtest is a `useMutation` whose result dies on unmount while the scan's cached result survives, so a route local pin would outlive what it describes. **Invalidation cannot re-run a mutation**, so the refresh action has to keep the last request body and call `mutate` again, which means the body is state this feature owns. And **`Banner` cannot carry the notice**: it is text only, documented "Never closable", and its three variants are static content, static content, and `role="alert"` errors, none of which a dynamic actionable notice is.

The engineer's choices matched both recommendations here, including keeping the trial counter running across a dataset change and labelling it with the dataset version rather than resetting it. That one is worth recording because resetting looks more principled and is in fact a loophole: a counter that clears when the data ticks lets an overfitting history be erased by waiting a day, which inverts the purpose of spec 0004.

## References

**Project sources** (verifiable, in this repo):
- `apps/web/src/components/shell/use-health.ts`: the single shell query pattern this feature copies, including its explicit `staleTime: Infinity` and `retry: 1`, and `isLive()`'s exact string check.
- `apps/web/src/components/shell/data-mode-banner.tsx`: the banner whose behaviour AC-6 protects, with its static synthetic default.
- `services/api/src/api/routes/catalog.py`: `/api/v1/meta` returning `MetaResponse` with `data: DataMeta | None`, which is why no contract change is needed.
- `engine/src/engine/contracts/market.py`: `DataMeta.end` and `data_version`, the two fields the change comparison uses.
- Spec `0011`: the server side change check with its 10 second floor, which sets the lower bound on how fast this can possibly be.
- Spec `0012`: the writer, which appends once a day, setting the frequency this is designed against.
- Spec `0004`: the trial counter keyed by rule structure in browser storage, extended here with the dataset version.
- Spec `0003`, AC-4: the one health query convention and the data mode signal.
- `docs/01-market-research-and-product-spec.md`: U-1 and U-2 on the data mode banner, U-5 on the warming state, and X-7's 25 second warm exit lab budget.
- `AGENTS.md`: TanStack Query already in the stack, and the static export on Vercel Hobby that makes a client side poll the natural fit.

**Practices & standards**:
- Poll when the event is rare and push when it is frequent, judged by what the host charges for rather than by which sounds more modern.
- Pin the data version your displayed results belong to, and compare against it, rather than trusting a clock.
- Never mutate what someone is reading without being asked; offer instead.
- Background refresh failures are silent, so that visible errors keep meaning something.
- Pause background work on a blurred tab, which TanStack Query does by default for `refetchInterval`.

**Measured in this repo**:
- TanStack Query is `^5.104.1` (`apps/web/package.json`), where `refetchIntervalInBackground` defaults to false, so the interval does not fire on a blurred tab. Confirmed against the installed version rather than assumed from a general claim about the library.
- `apps/web/src/components/banner.tsx` is text only with three variants and no action slot, which is what rules it out for the notice.
- `services/api/src/api/routes/catalog.py:37` returns `data=None` whenever no market is loaded, which is the case AC-8 covers.
- `Assumptions` (`engine/src/engine/contracts/backtest.py:108`) carries `seed` and `oos_start` and no dataset identity, which is what forces the contract change.

**Links** (web verified only):
- Pending the capped landscape check for this spec: AWS's statement of Lambda duration billing for response streaming. Cited by name until confirmed, and no URL is written here that was not fetched.
