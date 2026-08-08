# StreamPulse Engineering Journal

This document records the technical decisions, problems, and resolutions encountered while building StreamPulse, a near-real-time e-commerce order analytics pipeline with an integrated AI query agent.

---

## Phase 0 — Project Initialization

The repository was set up with a production-style structure before any application code was written: Git initialized with a `main` branch, a complete folder layout with `.gitkeep` placeholders, `.gitignore` configured before any real `.env` file existed, and placeholder documentation and Docker Compose configuration for Redpanda.

During setup, git appeared to show no pending changes after adding `.gitkeep` files. Rather than assuming a tooling problem, running `git status` and `git ls-files` confirmed the files were already tracked correctly. The broader lesson carried through the rest of the project: verify assumptions with git's own inspection commands before treating something as a bug.

---

## Phase 1 — Streaming Ingestion (Redpanda and Producer)

The Redpanda container initially entered a restart loop. The bind-mounted data directory had root ownership, and Redpanda runs as a non-root user, causing a permission error writing its pid file. The directory was recreated with open permissions for local development, with the understanding that a production setup would use proper UID-based ownership instead.

Topic retention configuration also proved unreliable: `rpk topic create --config retention.ms=...` did not apply the override, silently leaving the topic on the cluster's default retention. The fix was to apply retention with `rpk topic alter-config` after creation and verify the change with `describe`, confirming both the value and its source (`DYNAMIC_TOPIC_CONFIG`). This established a habit for the rest of the project: never trust a configuration command's exit code alone — verify the actual applied state.

A `ModuleNotFoundError` when running the producer directly was traced to Python's import path behavior when running a script from inside a subfolder. Adding `__init__.py` files and running modules with `python -m producer.produce_orders` from the project root resolved it, and this became the standard way every script in the project was executed afterward.

The producer was verified with controlled event bursts, graceful shutdown handling, and confirmed idempotent delivery to the `orders` topic with 48-hour retention.

---

## Phase 2 — Consumer, Dead Letter Queue, and First Deployment

The consumer was validated against real topic data rather than trusting a clean compile: 34 valid events landed correctly in DuckDB through idempotent inserts, with offsets committed only after a successful write. A deliberately malformed event was produced manually to confirm the rejection path — it was correctly routed to both the dead-letter topic and a queryable rejected-events table.

One practical Docker issue arose while testing this: piping input into a container with `docker exec -it` failed, because the `-t` flag allocates a TTY that conflicts with piped stdin. Using `-i` alone resolved it.

The first public deployment to Streamlit Community Cloud initially hung indefinitely during dependency installation. The cloud environment had defaulted to Python 3.14, a version newer than the one the project's dependencies were tested against, and packages without prebuilt wheels for that version were falling back to a slow source build. Explicitly pinning Python 3.12 in the deployment's advanced settings resolved it immediately. A second, related issue — the deployment installing the full project's dependency list, including packages unused by the dashboard itself — was resolved by scoping a separate `requirements.txt` to the Streamlit app's actual imports.

These two issues established a recurring theme for the project: cloud environments do not always match local assumptions, and the mismatch is often invisible until deployment.

---

## Phase 3 — dbt Transformation Layer and Alerts

Initializing dbt created its project folder in an unexpected location relative to the existing repository structure, and its default profile pointed at a new, empty database file rather than the pipeline's actual data. Both were corrected by moving files into place and explicitly verifying the connection target with `dbt debug` — a wrong path here fails silently, producing an empty database rather than an error.

A staging model and a materialized silver model were built with full dbt test coverage. On top of that, a unified alerts model was introduced, combining three independent signals into one structured table: data-quality issues surfaced from rejected events, high-value orders exceeding three times their region's average, and regional order-count spikes. At the dataset's initial small size, only the data-quality signal had fired — expected behavior given limited volume, not a defect, and this was later confirmed once real load testing produced enough data for the high-value-order rule to trigger correctly.

---

## Phase 4 — Testing, Load Verification, and Orchestration

Nineteen unit tests were added covering producer event generation and consumer logic, including a dedicated test proving the system's core reliability guarantee: producing the same order twice results in exactly one row, not two. Consumer tests intentionally used a real temporary DuckDB file per test rather than a mock, ensuring the actual SQL logic was exercised rather than assumed correct.

A sustained three-minute load test with the producer and consumer running concurrently showed stable memory (~230 MB, well under the container's 1 GB limit), consistent throughput of roughly 1.15 events per second, and zero data loss. A handful of events landed slightly after the consumer's timer expired due to independent duration limits between the two processes — expected behavior under the system's at-least-once, idempotent design, and correctly picked up on the next run rather than lost.

Airflow was introduced last, once the underlying pipeline was already proven stable, and deliberately configured in a lightweight standalone mode rather than the full multi-service stack used elsewhere — appropriate given the orchestration need was two sequential tasks, not a production multi-worker deployment. One early confusion was that newly added DAGs did not appear in `airflow dags list` until explicitly reserialized into the metadata database; Airflow does not scan the DAGs folder automatically on every CLI call. The orchestration was verified end to end, with both the dbt run and dbt test tasks completing successfully under Airflow's control.

---

## Phase 5 — Guardrailed AI Query Agent

The AI query agent converts natural-language questions into SQL using Gemini, validates the generated SQL against a strict allowlist before execution, and displays the query to the user alongside its results.

A code review of the initial implementation identified two issues worth fixing before building further on top of it. First, the guardrail validation function's return value was being discarded, meaning the code executed the original unvalidated SQL rather than the sanitized version — harmless today only because the current transformation was cosmetic, but a latent risk. Second, the SQL generator was being instantiated at module import time, which made the module difficult to test without a live API key and coupled import-time behavior to runtime configuration. Both were corrected, and twenty-five new tests were added covering the guardrail logic directly: allowed queries, disallowed tables (including when hidden inside joins or subqueries), every forbidden SQL operation, multi-statement injection attempts, and malformed input.

A smaller but instructive issue came up in the chat interface itself. The model's designed fallback for unanswerable questions is a SELECT statement with no table reference at all. The guardrail correctly allowed it through, but the resulting user-facing message read as a security warning rather than a graceful decline. The fix was interface-level, not a security change: recognizing the fallback message specifically and presenting it as a calm, informative response. The underlying lesson was that a check being technically correct is not the same as it being well communicated.

Connecting the deployed application to a cloud-hosted copy of the data, via MotherDuck, surfaced the most involved debugging arc of the project. Every authentication attempt failed with an "invalid token" error, despite the account being demonstrably active and working through MotherDuck's own web interface. Systematically ruling out token freshness, shell environment overrides, network connectivity, and system clock skew eventually pointed to the real cause: the installed DuckDB version was incompatible with MotherDuck's current server-side extension. Upgrading DuckDB resolved the authentication failures entirely, and the full test suite was re-verified afterward before trusting the change.

A related, quieter issue followed: once the MotherDuck token was available in the local environment, the test suite's runtime increased roughly fivefold, because tests were silently making real network calls instead of using the local file. An injectable connection factory was added so tests could explicitly force the offline path regardless of what credentials happened to be present in the environment — the same dependency-injection pattern already used elsewhere in the codebase.

The deployed application itself then failed with a different, cloud-specific error when attempting the identical MotherDuck connection that worked locally. After ruling out the most likely causes without success, a deliberate decision was made not to pursue open-ended third-party support for an issue with no clear resolution timeline, and instead to implement a graceful fallback: the application attempts the cloud connection first and falls back to an honest "no data available" state if it fails, rather than crashing. This was later found to have a simpler explanation than initially suspected — the token stored in the deployment's secret configuration did not match the one in local use. Correcting it resolved the live connection entirely, and the deployed application now serves real data end to end. A final, unrelated compatibility issue with a dataframe display parameter surfaced once real data began rendering, and was resolved by reverting to the previous parameter syntax.

---

## Phase 6 — Analytics Copilot

Following a successful query, a second model call generates a short plain-English summary of the results, grounded strictly in the data returned. The prompt explicitly prohibits causal language — attributing an outcome to a cause — unless the results themselves contain a column that supports such a claim, preventing the model from inventing explanations the data does not support.

Empty results are handled without an unnecessary model call, since there is nothing meaningful to summarize. Larger result sets are capped before being included in the prompt, with an explicit note of the true row count, to keep requests small and consistent in cost. If summary generation fails for any reason, the interface falls back to showing the results without a summary rather than failing the entire response — the explanation layer is treated as an enhancement, not a dependency.

Five tests were added covering the truncation behavior, the empty-result short-circuit, and correct data handling, all using a mocked model client to avoid real API calls during testing. In live use, a real query — total sales by region — produced an accurate, correctly ranked summary using only the returned figures, with no invented explanation for the pattern observed.

---

## Current Status

All phases through Phase 6 are complete, tested, and deployed. The project currently includes fifty automated tests, a fully orchestrated dbt pipeline, a guardrailed natural-language query interface, and a grounded analytics summary layer, all running against live data in production.
