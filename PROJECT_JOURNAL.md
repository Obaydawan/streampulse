# StreamPulse Project Journal

This journal records the engineering decisions, problems encountered, solutions implemented, and lessons learned throughout the project.

---

# Session 1 – Project Initialization

**Date:** 2026-08-01

## Objective

Set up a clean, production-style repository before writing any application code.

## Work Completed

- Created the `streampulse` project repository.
- Initialized Git and renamed the default branch to `main`.
- Created the complete folder structure.
- Added `.gitkeep` files to track empty directories.
- Configured `.gitignore` before creating any real `.env` file.
- Created `.env.example` with placeholder configuration.
- Added the initial `README.md`.
- Added the initial `docker-compose.yml` for Redpanda.
- Created placeholder Python files and documentation.

## Problems Encountered

- Initially attempted to create `.gitkeep` files from the home directory instead of the project directory.
- Git did not show any pending changes after creating `.gitkeep` files, which required verification.

## Cause

- Incorrect working directory.
- Needed to verify whether Git was already tracking the files.

## Solution

- Changed into the correct project directory.
- Verified tracked files using:

```bash
git ls-files
```

- Confirmed that `.gitkeep` files were already tracked.

## Lesson Learned

Before assuming Git has a problem:

- Verify the current working directory.
- Use `git status` to inspect the repository state.
- Use `git ls-files` to confirm which files are already tracked.

Avoid making assumptions—verify with Git's own tools first.

## Session — Phase 1 Complete (Redpanda + Producer)

**Problem:** Redpanda container was restart-looping on startup.
**Cause:** Bind-mounted `redpanda-data/` directory had root ownership; Redpanda runs as a non-root container user and got a Permission Denied error writing its pid file.
**Solution:** Recreated the directory and `chmod 777`'d it (local dev only — would use proper UID ownership in production).
**Lesson:** Bind-mounted volumes need explicit permission handling for non-root containers; don't assume default directory permissions will work.

**Problem:** `rpk topic create --config retention.ms=...` silently didn't apply the override — topic came up with the 7-day cluster default instead.
**Cause:** The `--config` flag on `topic create` doesn't behave as expected in this Redpanda version/setup for `retention.ms`.
**Solution:** Used `rpk topic alter-config` after creation instead, and verified `SOURCE` changed to `DYNAMIC_TOPIC_CONFIG` to confirm it actually took effect.
**Lesson:** Never trust a config flag silently — always verify with `describe` that the value AND its source are what you expect, not just that the command exited 0.

**Problem:** Producer script threw `ModuleNotFoundError: No module named 'shared'` when run directly.
**Cause:** Running `python producer/produce_orders.py` puts the `producer/` folder itself on the import path, not the project root, so sibling package `shared/` wasn't visible.
**Solution:** Added `producer/__init__.py` and ran the script as a module from the project root: `python -m producer.produce_orders`.
**Lesson:** Multi-package Python projects should be run with `-m` from the root, not as bare scripts from inside a subfolder.

**Result:** Producer verified working — controlled bursts via `--max-events`/`--duration`, graceful Ctrl+C shutdown with full flush, idempotent delivery confirmed, events landing correctly in the `orders` topic with 48h retention.

## Session — Phase 2.1 Complete (Consumer + DLQ)

**Problem:** Needed to verify the consumer actually processes events correctly, not just that it compiles.
**Solution:** Ran it against real topic data — 34 valid events landed correctly in DuckDB `bronze_orders` via idempotent `ON CONFLICT DO NOTHING` inserts, offsets committed only after successful writes.
**Lesson:** "Compiles cleanly" and "works correctly" are different bars — always run against real data before calling a component done.

**Problem:** Needed to verify the rejection path (DLQ + rejected_events table) actually triggers on bad data.
**Solution:** Manually produced one deliberately invalid event (negative price) directly into the topic via `rpk topic produce`, then confirmed it was correctly rejected, published to `orders_dlq` with a `reason` header, and logged into the `rejected_events` DuckDB table.
**Lesson:** `docker exec -it` fails when piping stdin via heredoc (`<<<`) because `-t` allocates a TTY that conflicts with piped input — use `-i` only, not `-it`, when piping data into a container command.

**Result:** Consumer verified end-to-end — valid events land correctly, invalid events are caught by schema validation and routed to both the DLQ topic and a queryable DuckDB table, offset-commit-after-write guarantees at-least-once delivery with idempotent inserts making duplicates harmless.

## Session — Phase 2.4 Complete (First Public Deployment)

**Problem:** Streamlit Cloud build hung indefinitely at dependency installation, no clear error in logs.
**Cause:** Cloud environment defaulted to Python 3.14.6 (very new), and pinned packages like pandas/duckdb likely lacked prebuilt wheels for that version, forcing a slow/stuck source compile on the free-tier build machine.
**Solution:** Deleted and redeployed with Python 3.12 explicitly selected in Advanced Settings — matched the version the dependencies were actually tested against. Build completed in under a minute.
**Lesson:** Cloud platforms may default to a newer Python version than your local dev environment. Always check for a Python version override option when a build silently hangs during dependency install, rather than assuming it's a network or resource problem.

**Problem:** Also fixed — Streamlit Cloud building the FULL project requirements.txt (including confluent-kafka, unused by the dashboard) caused unnecessary slow builds.
**Solution:** Added a scoped `streamlit_app/requirements.txt` containing only what app.py actually imports (streamlit, duckdb, python-dotenv, pandas). Streamlit Cloud prioritizes a requirements.txt in the same folder as the main app file.
**Lesson:** Don't make a deployment install dependencies the deployed code doesn't use — scope requirements files per-component in a multi-part project.

**Result:** First public deployment live and working correctly. Confirms the deployment pipeline itself (GitHub → Streamlit Cloud → live app) functions end-to-end. App correctly shows a "no database" message rather than crashing, since the cloud environment has no access to the local DuckDB file yet — an architecture gap to be addressed in a later phase, not a bug in this one.

**Live URL:** https://streampulse.streamlit.app/

## Session — Phase 3.1 Complete (dbt Silver Layer)

**Problem:** `dbt init` created the project as a top-level `streampulse_dbt/` folder instead of inside the existing `dbt/` directory from Phase 0's structure.
**Solution:** Moved all generated files into `dbt/` and removed the now-empty top-level folder.
**Lesson:** dbt's init command always creates a new folder named after the project — plan to move it into your intended structure immediately, don't assume it lands where you want.

**Problem:** `profiles.yml` defaulted to a brand-new `dev.duckdb` file instead of the real `data/orders.duckdb` where actual pipeline data lives.
**Solution:** Manually edited the profile to point at `../data/orders.duckdb` (relative to the dbt/ folder), confirmed via `dbt debug`.
**Lesson:** Always verify dbt's connection target explicitly with `dbt debug` before running anything — a wrong path fails silently by just querying/creating an empty database instead of erroring.

**Problem:** Editing dbt_project.yml with nano while also trying to paste a heredoc block caused the literal `cat >`/`EOF` shell syntax to get written into the YAML file itself as text, breaking the YAML parser.
**Solution:** Recreated the file using a heredoc pasted directly at the shell prompt, never inside an open editor.
**Lesson:** Never mix nano and heredoc pastes in the same step — pick one method and stick to it for that edit.

**Result:** dbt project set up and connected to the real pipeline database. Built two models: `stg_orders` (typed staging view) and `silver_orders` (materialized table with derived `order_total`). All 4 dbt tests pass (not_null + unique on order_id, both layers). silver_orders is materialized as a table (not view) since it will be queried repeatedly by the dashboard and Alerts panel.

## Session — Phase 3.2 Complete (Alerts Panel)

**Result:** Built a unified `alerts` dbt model combining three signal sources into one structured table (alert_id, timestamp, severity, region, alert_type, reason):
  1. `data_quality` — surfaces Phase 2's rejected_events (schema/validation failures)
  2. `high_value_order` — flags orders >3x their region's average total
  3. `region_spike` — flags a region with order count >1.5x the cross-region average

All fields tested with dbt (not_null, unique, accepted_values on severity/alert_type).
Wired into Streamlit as a color-highlighted Alerts panel, verified locally
against real data — correctly surfaced the one existing data_quality alert
from Phase 2 testing. high_value_order and region_spike show zero alerts
currently, which is expected given the small, low-variance test dataset —
not a bug, the thresholds simply haven't been crossed yet.

**Lesson:** dbt's `accepted_values` test syntax changed — values must now be
nested under an `arguments:` key, not passed as top-level test config, to
avoid a deprecation warning in dbt 1.12+.

## Session — Phase 4.1 Complete (pytest Coverage)

**Result:** Added 19 unit tests covering producer and consumer logic.
Producer tests (7): event generation correctness — required fields present,
price/quantity in valid ranges, region/product from known lists, order_id
uniqueness, deterministic product_id mapping.
Consumer tests (12): schema validation (valid event, missing field, negative
price, zero quantity, bad timestamp, empty string field), real-DuckDB table
creation, event insertion, and — most importantly — a direct test proving
the idempotent insert guarantee: producing the same order_id twice results
in exactly one row, not two. DLQ interaction tested via mocked producer
(no live broker needed for unit tests).

**Approach:** Consumer tests use a real temporary DuckDB file per test
(pytest's tmp_path fixture) rather than a mocked database, specifically so
the actual SQL (schema creation, ON CONFLICT DO NOTHING logic) gets
exercised — a mock would have let a real SQL bug pass silently.

**Result:** All 19 tests pass. This formally verifies the core reliability
guarantee stated in the original project plan: duplicate/at-least-once
delivery is made harmless by idempotent inserts, not just assumed to work.

## Session — Phase 4.2 Complete (Sustained Load Test)

**Result:** Ran producer + consumer concurrently for 180s each, measuring
memory, CPU, throughput, and disk growth throughout.
- Throughput: ~1.15 events/sec sustained
- Memory: stable at ~230-231 MiB (well under the 1GiB container cap), no
  leak visible over the test window
- 207 new events processed, 0 rejected, 0 lost
- 9 events landed after the consumer's timer expired before the producer's
  did — expected behavior given independent duration limits, not a bug;
  correctly picked up on the very next consumer run, proving the
  at-least-once + idempotent design handles this real scenario correctly
- dbt full rebuild: under 9 seconds for all 3 models against 242 rows
- Alerts model at scale: high_value_order rule triggered for the first
  time (8 alerts) with real volume, confirming the detection logic works
  correctly under load rather than only in small-sample testing

**Lesson:** Running producer/consumer with independent duration timers can
leave a small gap of unconsumed events when they don't start/stop in sync —
this is expected and harmless given the at-least-once + idempotent insert
design, but worth knowing rather than assuming timers must be synchronized.

Full metrics: see phase4_2_metrics.txt

## Session — Phase 4.3 (Airflow Install)

**Problem:** Installing apache-airflow==3.3.0 silently upgraded two shared
dependencies — pathspec (0.9→1.1.1) and more-itertools (10.8.0→11.1.0) —
past the version ranges dbt-core and metricflow require. pip printed
dependency-conflict warnings but completed the install anyway rather than
blocking it.
**Cause:** pip's resolver doesn't always catch cross-package version
conflicts introduced by a large dependency tree like Airflow's, even when
it detects and reports them after the fact.
**Solution:** Manually re-pinned pathspec and more-itertools to the ranges
dbt-core/metricflow require, then re-ran the full verification suite (dbt
run, dbt test, python compile checks, and all 19 pytest tests) to confirm
nothing regressed before trusting the environment again.
**Lesson:** Never assume a clean "Successfully installed" pip message means
the environment is actually healthy — always check for dependency-conflict
warnings in the output, and re-verify existing functionality after adding
any large new dependency like Airflow, even if the install itself appeared
to succeed.

## Session — Phase 4.3 Complete (Airflow Orchestration)

**Result:** Set up Airflow 3.3.0 in standalone-appropriate configuration
(SQLite metadata DB, no separate scheduler/worker/Postgres/Redis stack) —
a deliberate scope decision to match the actual orchestration need: two
sequential tasks, not a production multi-worker deployment. This differs
intentionally from TransactSafe's full CeleryExecutor Airflow stack,
which is appropriate there but would be over-engineering here.

DAG (`streampulse_dbt_pipeline`) orchestrates exactly two tasks:
dbt_run >> dbt_test. Nothing more, per project scope.

**Problem:** `airflow dags list` repeatedly showed "No data found" even
after the DAG file was correctly placed and pointed to.
**Cause:** Airflow doesn't scan the dags_folder automatically on every
CLI call — DAGs need to be explicitly serialized into the metadata DB
first (`airflow dags reserialize`) before `dags list` will show them.
**Lesson:** Don't assume "file exists in dags_folder" means "Airflow
knows about it" — always force a reserialize after DAG changes when
testing via CLI rather than a live scheduler.

**Problem:** Default Airflow install loads ~80 example DAGs, cluttering
every dags list/UI view.
**Solution:** Set load_examples = False in airflow.cfg, then a full
`airflow db reset` + `airflow db migrate` to clear the already-registered
example DAGs out of the metadata DB.

**Result:** Verified end-to-end via `airflow dags test streampulse_dbt_pipeline`
— both dbt_run and dbt_test tasks completed successfully (state=success),
DagRun marked successful. This proves Airflow can correctly orchestrate
the real dbt project, not just a toy example.

## Session — Phase 5 Progress (AI Agent Review + Testing)

**Context:** AI agent core (Gemini integration, prompt engineering, guardrails,
executor) was built in a separate session. This session's work: full code
review of all AI agent files, one bug fix, and comprehensive pytest coverage.

**Problem:** `executor.py` called `validate_sql(sql)` without capturing its
return value, then executed the original unvalidated `sql` variable. Worked
today only because validate_sql's current transformation (semicolon strip)
is cosmetic — a future guardrail change that sanitizes/rewrites SQL would
silently execute the wrong query.
**Solution:** Changed to `sql = validate_sql(sql)`.

**Problem:** `SQLGenerator()` was instantiated at module import time in
executor.py, meaning every import created a real Gemini client and would
fail immediately if GEMINI_API_KEY was missing — made the module hard to
unit test without hitting the real API or requiring a key just to import.
**Solution:** Added optional `generator` parameter to `execute_question()`
for dependency injection, defaulting to lazy instantiation only when the
function actually runs.

**Result:** 25 new tests added covering guardrails.py (21 tests: allowed
queries, disallowed tables including inside JOINs/subqueries, every
forbidden SQL operation, PRAGMA, multi-statement injection, malformed
input) and executor.py (4 tests, using a mocked generator so no real API
calls are made during testing — protects free-tier quota). All tests pass.
Confirmed the guardrail correctly catches PRAGMA statements as a side
effect of the exp.Select isinstance check, not a gap in forbidden_types.

**Lesson:** Discarding a validation function's return value is an easy,
easy-to-miss bug when the function currently happens to be a no-op
transformation — always capture and use validated/sanitized output
explicitly, never assume "it works today" means "the contract is honored."

## Session — Phase 5 UI Complete (AI Chat Interface)

**Problem:** The model's designed "I can't answer that" fallback is a
tableless SELECT literal (no FROM clause). The guardrail correctly let it
through, but the original error message ("Query does not reference any
known table") displayed as a red warning — technically accurate but
confusing, since this is a safe, intended behavior, not a security block.
**Solution:** Removed the unnecessary "must reference at least one table"
check from guardrails.py (a tableless SELECT can't touch any data, so it's
safe by construction). Added a dedicated UI state in ai_chat.py that
detects the fallback message specifically and displays it as a calm info
box ("I don't have the data to answer that") rather than a warning.

**Result:** Built streamlit_app/ai_chat.py — full chat interface showing
generated SQL before/with results, a results table, graceful handling of
three distinct outcomes: successful query, "can't answer this" fallback,
and genuine guardrail block (bad/disallowed SQL). Verified all three paths
live: "What's the average order value by region?" (real grouped results),
"How many orders are there?" (242, matches known total), and "Show me
everything from bronze_orders" (correctly declined without exposing raw
data or looking like an error).

**Lesson:** A safety check being technically correct isn't the same as
being well-communicated — the guardrail blocking the fallback message
was "working as designed" but the resulting UX looked like a bug. Worth
distinguishing "the system correctly declined" from "the system errored"
in user-facing messaging, even when both pass through similar code paths.

## Session — MotherDuck Cloud Sync Complete (Phase 5 Deployment)

**Problem:** MotherDuck connection failed with "Invalid token or user" across
every method tried (fresh tokens, env vars, connection strings, even
browser-based auth with no token at all) despite a genuinely valid,
active MotherDuck account (confirmed working in their web UI).
**Cause:** DuckDB 1.4.0 was incompatible with MotherDuck's current server-side
extension version — an infrastructure version mismatch, not a credentials
or configuration error.
**Solution:** Upgraded duckdb 1.4.0 -> 1.5.5 project-wide. Full regression
suite (45 tests, dbt run + test) re-verified clean after the upgrade
before trusting it.
**Lesson:** When every authentication method fails identically regardless
of the credential used, suspect the client library/extension version
before assuming the credential itself is wrong — a systematic failure
pattern across multiple independent auth paths points to infrastructure,
not configuration.

**Result:** Real pipeline data (bronze_orders, rejected_events) synced to
MotherDuck. dbt run --target prod builds stg_orders/silver_orders/alerts
directly in the cloud database from the synced data. app.py and
executor.py both updated to prefer MotherDuck (via MOTHERDUCK_TOKEN) when
available, falling back to the local file for local development.

**Problem:** After wiring MOTHERDUCK_TOKEN into executor.py, the full test
suite slowed from ~4s to ~23s — tests were silently making real network
calls to MotherDuck instead of using the local file, since the token was
present in the local .env.
**Solution:** Added an injectable connection_factory parameter to
execute_question(), same dependency-injection pattern already used for
the SQL generator. Tests now explicitly force the local-file connection,
staying fast and offline regardless of what's in the environment.
**Lesson:** A "prefer cloud, fall back to local" connection strategy is
correct for production code but dangerous for tests if not made
explicitly overridable — environment-dependent test behavior is a subtle
trap that can silently slow down or add network dependencies to a test
suite that's supposed to be fast and isolated.

## Session — MotherDuck Cloud Deployment: Partial Success, Graceful Fallback

**Problem:** After fixing the DuckDB/MotherDuck version incompatibility and
confirming the connection worked reliably from the local machine (sync
script, dbt --target prod, direct queries all succeeded), the deployed
Streamlit Cloud app failed with a different error: "PERMISSION_DENIED,
RPC 'CREATE_SLT'" when attempting the identical connection.
**Investigation:** Ruled out read_only parameter mismatch (tested locally
with read_only=True — succeeded). Ruled out token issues (same token
works locally). Root cause is most likely infrastructure-specific to
MotherCuck's free-tier account/session provisioning when connecting from
Streamlit Cloud's environment (possible region mismatch, IP-based
restriction, or free-tier session limits on external/service-based
connections) — not diagnosable further from the client side without
MotherDuck's server-side logs.
**Decision:** Rather than pursue MotherDuck support (uncertain timeline,
uncertain resolution, diminishing returns for a portfolio project), added
a try/except fallback in both app.py and executor.py's get_connection().
The app now attempts MotherDuck first, and gracefully falls back to the
local-file behavior (including the honest "no database found" message)
if the cloud connection fails for any reason, rather than crashing.

**Result:** MotherDuck sync and cloud dbt run remain genuinely working and
demonstrable locally — this is real, working infrastructure, just not
currently reachable from the specific Streamlit Cloud environment. The
deployed app degrades gracefully instead of showing a raw stack trace.

**Lesson:** Not every integration needs to be pushed to full production
resolution to be worth building — the local MotherDuck pipeline (sync +
cloud dbt transforms) is real, tested, working engineering, and the
graceful-degradation pattern itself is a legitimate, portfolio-worthy
design decision. Knowing when to stop debugging a third-party service
issue and ship a resilient fallback instead is itself an engineering
judgment call worth documenting, not a failure to hide.

## Session — Phase 6 Complete (Analytics Copilot)

**Result:** Added ai_agent/explain.py — after a successful query, a second
Gemini call generates a 1-3 sentence plain-English summary of the results,
grounded strictly in the returned data. The prompt explicitly forbids
causal language ("because", "due to") unless the results themselves
contain a column that supports it, preventing the model from inventing
explanations the data doesn't support.

Design decisions:
- Empty results short-circuit before calling Gemini at all (nothing to
  explain, no reason to spend an API call)
- Large result sets are capped at 30 rows in the prompt, with an explicit
  note of the true total row count, to keep prompts small and cheap
- The explanation is generated once per query (at insert-into-history
  time), not regenerated on every Streamlit re-render
- If explanation generation fails for any reason, the app falls back to
  showing results without a summary rather than breaking the whole
  response — the explanation is an enhancement, not a dependency

**Testing:** 5 new tests using a mocked GeminiClient — verified the
truncation logic, the empty-result short-circuit (and that it correctly
avoids an unnecessary API call), response whitespace handling, and that
the correct data is actually passed into the prompt. All 50 project tests
pass.

**Verified live:** "What's total sales by region?" produced a correct,
data-grounded summary ranking all five regions accurately with real
numbers, no invented causes — confirming the guardrail-style prompt
design works in practice, not just in isolated tests.
