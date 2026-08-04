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
