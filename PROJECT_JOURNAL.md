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
