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
