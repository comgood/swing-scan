# 01a: Free Data Sources (Week-1 Edition)

| | |
|---|---|
| **Date** | 2026-10-06 |
| **Status** | **v2.1** (live mode = 2016+). Trimmed per `03-devils-advocate-review.md` §6.1 item 4. The full v1 survey is in git history. |
| **Frame** | $0, non-commercial portfolio project, public repo, ≤ 1 week. The public demo is **synthetic only** (see doc 01 §6.1). |

> Free-tier limits change often (Alpha Vantage cut to 25/day in 2025; Stooq added an API key in 2026; Yahoo throttles). Re-check anything marked *verify*.

---

## 1. Week-1 decision

| Use | Source | Why |
|---|---|---|
| **Public demo, video, CI, fixtures** | **Synthetic generator** (doc 01 §6.1) | No licence issues. Planted delistings and splits give a known ground truth for tests. |
| **Personal mode (local only)** | **Alpaca Market Data, free Basic plan** | See §2 |

Everything else is **Later** (§3).

---

## 2. Alpaca free plan: facts for personal mode

| Item | Detail |
|---|---|
| Account | Free Alpaca account; a **paper** account is enough |
| History | Daily bars **since 2016-01-04** |
| Feed | Full-market **SIP** bars for any period ending ≥ 15 min ago, identical to the paid plan for historical data. Pass `feed=sip`. |
| Adjustment | `adjustment=all` → split- and dividend-adjusted (matches our adjusted-only engine) |
| Rate limit | **200 calls/min**; multi-symbol bars endpoint with pagination |
| Fetch range | **Full history: 2016-01-04 → latest close** for ~500 current S&P 500 names + SPY (doc 01 v3 §6.1) |
| Fetch cost | ~500 tickers × ~2,700 bars ≈ 1.35M bars, so **a few minutes** at 200 calls/min |
| **Survivorship** | **Survivors only.** Inactive/delisted symbols return no bars, and data stops at delisting. Backtests are biased upward. **Acceptable for learning if the UI labels it** ("Real data: survivors only"). |
| Known quirks | Occasional symbol-reuse mix-ups (forum report: ticker "Q" combined two companies). Spot-check outliers. |
| **Terms** | Treat as **personal, non-commercial use only** (redistribution terms not verified). Real data never leaves the owner's machine and is never committed. |

**Handling rules (in AGENTS.md and enforced by the guard):**
- Keys only in env vars.
- `data/` and `research/` (private live research notes) are gitignored. Metrics derived from live data are never published.
- `DATA_MODE=live` runs only on localhost.
- No recorded HTTP cassettes or fixtures from vendor responses.
- The demo video is synthetic-only.

---

## 3. Later options (not week 1)

| Need | Source | Licence note |
|---|---|---|
| Survivorship-bias-free real prices (last 2 yrs + growing archive) | **Massive (formerly Polygon) Basic**: Grouped Daily = whole market in 1 call; reference tickers incl. inactive; splits/dividends; 5 calls/min | Personal only: Massive requires a Business plan as soon as anyone else (incl. testers) sees data or derived values |
| Pre-2016 history (survivors) | **Stooq** bulk ZIP (API key since 2026) | Personal use |
| Fundamentals, point-in-time | **SEC EDGAR** `companyfacts` + Financial Statement Data Sets (`filed` dates); ≤ 10 req/s with a contact User-Agent | **Public data, can be shown** |
| Historical earnings dates | **SEC 8-K Item 2.02** filings (acceptance timestamp: before open vs after close) | Public |
| Sectors | **SEC SIC codes** (submissions API) | Public |
| Listings / delisting dates | **Nasdaq Trader Symbol Directory** (daily files); SEC Form 25 | Public |
| Risk-free rate | **FRED** DTB3 (free key, 120 req/min) | Public domain series |
| Trading calendar | `exchange_calendars` / `pandas_market_calendars` | Open source |

---

## Appendix A: Condensed comparison of free price sources

| Source | Free history | Delisted? | Limit | Full-market daily refresh feasible? | Verdict |
|---|---|---|---|---|---|
| **Alpaca Basic** | 2016+ | No | 200/min, multi-symbol | Yes | **Week-1 personal mode** |
| **Massive Basic** | 2 yrs | **Yes** (Grouped Daily) | 5/min, 1 call per day for the whole market | Yes | Later: bias-free window |
| **Stooq** | Decades | Unknown (assume no) | Daily quota; bulk ZIP | Bulk only | Later: deep history |
| **Tiingo free** | Decades | Yes | 500 unique symbols/month | No | Later: delisted fill-in |
| **Yahoo (`yfinance`)** | Decades | No | Unofficial, 429 blocks | Unreliable | Spot checks only |
| **Alpha Vantage** | Full | No | 25/day; adjusted endpoint is premium | No | Not suitable |
| **FMP** | EOD (*verify* depth) | Partial | 250/day | No | Not suitable |
| **Twelve Data** | 30+ yrs | No | 800/day, 8/min | No | Not suitable |
| **EODHD** | 1 yr | Paid only | 20/day | No | Not suitable |
| **Finnhub** | Candles not free (*verify*) | No | 60/min | n/a | Earnings calendar only |

**Licensing:** every free *price* source above is personal or non-commercial use only. Only public-sector data (SEC, FRED, Nasdaq Trader listings) may be shown publicly.

---

## Sources
- Alpaca: https://docs.alpaca.markets/docs/about-market-data-api ; https://docs.alpaca.markets/us/docs/market-data-faq ; https://forum.alpaca.markets/t/get-historical-data-for-inactive-stocks/10097 ; https://forum.alpaca.markets/t/fixing-data-historical-bars-of-symbol-q-are-comprised-of-two-different-stocks/18184
- Massive: https://massive.com/pricing ; https://massive.com/knowledge-base/article/which-plan-do-i-need-to-show-massive-data-in-my-app ; https://massive.com/legal/individuals-terms-of-service
- Tiingo: https://www.lambdafin.com/articles/financial-data-api-2026 ; https://github.com/business-science/riingo
- Stooq: https://providers.apievangelist.com/providers/stooq/
- Yahoo: https://usahousinginformation.com/yahoo-finance-too-many-requests/
- Alpha Vantage: https://www.macroption.com/alpha-vantage-api-limits/
- FMP / Twelve Data / EODHD / Finnhub: https://qveris.ai/guides/stock-api-free-comparison/ ; https://www.codewords.ai/blog/twelve-data-api ; https://www.chartoasis.com/how-to-use-eodhd-com-even-for-free-cop3 ; https://apicostcalc.com/finnhub.html
- SEC EDGAR: https://www.sec.gov/edgar/searchedgar/accessing-edgar-data.htm ; https://www.sec.gov/data/financial-statement-data-sets ; https://sec-api.io/resources/form-8-k-item-2-02-exhibit-99-earnings-announcements-explained-how-to-get-the-data
- Nasdaq Trader: https://www.nasdaqtrader.com/Trader.aspx?id=Help
- FRED: https://fred.stlouisfed.org/series/dtb3
