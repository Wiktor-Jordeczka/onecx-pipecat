# Pipecat Application Foundation (#589) — Verify-and-Close Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Confirm that the Pipecat application foundation for issue #589 is fully implemented and every acceptance criterion holds, and close the issue without re-authoring work that is already committed.

**Architecture:** This is a **verify-and-close** plan, not a build plan. The checked-out branch `feat/issue-onecx-pipecat-589-4` already contains the complete #589 implementation, added by commit `ada4fd4` (config, models, six adapters, factory, container, FastAPI app, `main`, tests, CI, Antora docs, `uv.lock`) and completed by commit `310ec68` (`tests/test_factory.py`, `tests/test_main.py`). The local working tree is clean and, as verified during planning, the full CI command set passes (ruff check, ruff format, 21 pytest tests) and the server boots and serves `/healthz` over a real socket. The only acceptance criterion that cannot be run locally (the Antora CI docs job) is exercised here locally with Node/npm present as the closest authority.

**Tech Stack:** Python 3.11+ (3.12 used), `uv` package manager, `pytest` + `pytest-asyncio` (`asyncio_mode = "auto"`), `ruff` (lint + format), FastAPI + `uvicorn` + `httpx` (ASGI), `pydantic`/`pydantic-settings`, `pipecat-ai`, Antora (docs, `npm install -g antora@3.x`), GitHub Actions.

**Spec:** GitHub issue `onecx/internal-tasks#589` — "Establish the Pipecat application foundation." Parent `#587` is the scope boundary. No sibling context was loaded.

## Global Constraints

- **Do not rewrite, restructure, or re-`git add` the already-committed application.** The work is committed on the branch; the plan's deliverable is verified, not re-created.
- **Python floor `>=3.11,<4.0`** (`pyproject.toml`). All commands pin `--python 3.12` to match `.github/workflows/ci.yml` and `README.md`.
- **Exact CI commands** (from `.github/workflows/ci.yml`) are the authority for pass/fail:
  - `uv sync --python 3.12 --frozen`
  - `uv run --python 3.12 ruff check .`
  - `uv run --python 3.12 ruff format --check .`
  - `uv run --python 3.12 pytest -q`
- **No cloud credentials** may be required by tests or CI (verified: no `secrets.` / token / provider references in `ci.yml`; all adapters are in-memory).
- **`uv`** must be on `PATH`. In this environment it is at `/home/runner/.local/bin/uv` and is importable via `python3 -m uv`. Prefix commands with `export PATH="/home/runner/.local/bin:$PATH"` if `uv` is not already resolvable.
- **`uv.lock` is pinned**; always use `--frozen` on sync so the exact locked set (including `pipecat-ai`) is installed, not re-resolved.
- Any **code change** introduced by a fix step MUST leave `ruff check .`, `ruff format --check .`, and `pytest -q` all green before the issue is closed.

---

## Problem Statement

Issue #589 asks for a runnable Pipecat application foundation that supports incremental delivery of authenticated voice sessions through replaceable adapters. Its acceptance criteria are: the app installs/runs/tests through `uv`; `pytest` + `pytest-asyncio` run an asynchronous health-path test; typed configuration and replaceable adapter interfaces exist for authentication, Agent Configuration, speech, persistence, Permission, and MCP; CI verifies tests and static checks with no external cloud credentials; and Antora documentation covers local setup, configuration, and the adapter interfaces.

**Ground truth (verified in this repo):** Every one of those deliverables is already present and passing. `onecx_pipecat/` contains `config.py` (typed nested `Settings`), `models.py` (typed domain value models), `adapters/` (six `Protocol` interfaces + in-memory implementations for all six capabilities), `adapters/factory.py` (the single swap point per capability), `container.py` (`AppContainer`), `app.py` (FastAPI with `/healthz`), and `main.py` (uvicorn entrypoint). `tests/` has seven async/sync test modules. `.github/workflows/ci.yml` runs the test/lint/format + docs jobs with no credentials. `docs/` is a complete Antora module (nav + four pages + component descriptor + `antora-playbook.yml`).

Verified outcomes:
- `uv sync --python 3.12 --frozen` — installs cleanly (lockfile resolves, `pipecat-ai 1.8.1` installed).
- `uv run --python 3.12 ruff check .` — "All checks passed!"
- `uv run --python 3.12 ruff format --check .` — "22 files already formatted."
- `uv run --python 3.12 pytest -q` — **21 passed in ~2.3 s**.
- `tests/test_app.py::test_healthz_returns_ok_with_adapter_summary` runs under `asyncio: mode=Mode.AUTO` (pytest-asyncio 0.26.0) — the asynchronous health-path test.
- `uv run --python 3.12 uvicorn onecx_pipecat.main:app --port 8099` boots; `GET /healthz` → HTTP 200 JSON with `"status": "OK"`, app name, `pipecat_version`, and all seven adapter names; `GET /does-not-exist` → HTTP 404.
- `.github/workflows/ci.yml` contains no credential/secret/provider references.

The end state for this issue is: **confirmed complete and verified** — no new code is required. The tasks below are verification/acceptance checks (with one docs-build check), a regression gate, and a single commit only if a fix is forced by a failing check.

## Approach

Treat the existing implementation as the source of truth and prove it satisfies each acceptance criterion by running the exact CI command set plus two locally-runnable criteria not covered by a single `pytest` invocation (the "runs" criterion via a live socket, and the Antora docs-build criterion via Node/npm, which are present here). Because the branch is clean and passing, the expected outcome of every task is green with no edits. Two tasks encode concrete fixes **only to apply if their gate fails** (these are not expected to fire). This keeps the plan executable-as-written and deterministic while remaining a real safety net.

## File-Level Task List

No files are created or modified in the happy path. The file references below are the files each verification task exercises and, for the two fix tasks, the single file that a fix (if needed) would touch.

### Task 1: Verify install, static checks, and the async test suite

**Files:**
- Read (verify only): `pyproject.toml`, `.github/workflows/ci.yml`, `onecx_pipecat/**`, `tests/**`

**Interfaces:**
- Consumes: the committed application on the branch.
- Produces: a recorded pass/fail for the `uv sync` + `ruff` + `pytest` triple; the test count (expected 21).

- [ ] **Step 1: Ensure `uv` is on PATH**

Run: `export PATH="/home/runner/.local/bin:$PATH" && uv --version`
Expected: prints a `uv` version (e.g. `uv 0.12.10`).

- [ ] **Step 2: Install the pinned dependency set**

Run: `uv sync --python 3.12 --frozen`
Expected: exit 0; a venv with all locked packages including `pipecat-ai`.

- [ ] **Step 3: Run lint and format checks (the CI static gates)**

Run: `uv run --python 3.12 ruff check .` then `uv run --python 3.12 ruff format --check .`
Expected: `All checks passed!` and `22 files already formatted.`

- [ ] **Step 4: Run the full test suite (async mode active)**

Run: `uv run --python 3.12 pytest -q`
Expected: `21 passed`. The banner reports `plugins: asyncio-...` and `asyncio: mode=Mode.AUTO`, proving `pytest-asyncio` is driving the async tests.

- [ ] **Step 5: Confirm the asynchronous health-path test by name**

Run: `uv run --python 3.12 pytest tests/test_app.py -v`
Expected: `tests/test_app.py::test_healthz_returns_ok_with_adapter_summary PASSED` (an `async def` test executed under `asyncio` mode).

- [ ] **Step 6: Commit (no-op if clean)**

Run: `git status --porcelain`
Expected: empty (no changes). If a fix was required in Task 8, that fix is committed there instead. Do not commit anything here in the expected path.

**Dependencies:** None.

### Task 2: Verify the app runs and serves the health path over a real socket

**Files:**
- Read (verify only): `onecx_pipecat/main.py`, `onecx_pipecat/app.py`, `onecx_pipecat/container.py`

**Interfaces:**
- Consumes: `onecx_pipecat.main:app` (module-level FastAPI instance) and `onecx_pipecat.container.AppContainer`.
- Produces: proof that the "runs" criterion holds — a live HTTP 200 `/healthz` with the adapter summary, and HTTP 404 for an unknown path.

- [ ] **Step 1: Start the server in the background on a free port**

Run:
```bash
export PATH="/home/runner/.local/bin:$PATH"
uv run --python 3.12 uvicorn onecx_pipecat.main:app --port 8099 >/tmp/uvicorn_boot.log 2>&1 &
SRV_PID=$!
for i in $(seq 1 40); do
  curl -s -o /dev/null http://127.0.0.1:8099/healthz 2>/dev/null && break
  sleep 0.5
done
```
Expected: the readiness loop exits with a successful curl (server is up).

- [ ] **Step 2: Assert the health-path response body**

Run:
```bash
curl -s http://127.0.0.1:8099/healthz | python3 -m json.tool
```
Expected: `"status": "OK"`, `"app": "onecx-pipecat"`, a non-empty `"pipecat_version"`, and an `"adapters"` object whose values are `InMemoryAuthAdapter`, `InMemoryAgentConfigAdapter`, `InMemorySttAdapter`, `InMemoryTtsAdapter`, `InMemoryPersistence`, `InMemoryPermissionAdapter`, `InMemoryMcpAdapter`.

- [ ] **Step 3: Assert an unknown path is rejected**

Run: `curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8099/does-not-exist`
Expected: `404`.

- [ ] **Step 4: Stop the server**

Run: `kill $SRV_PID 2>/dev/null; wait $SRV_PID 2>/dev/null; echo stopped`
Expected: `stopped`, and `/tmp/uvicorn_boot.log` shows `Application startup complete` and a `"GET /healthz HTTP/1.1" 200 OK` line.

**Dependencies:** Task 1 (deps installed).

### Task 3: Verify typed configuration and the six replaceable adapter interfaces

**Files:**
- Read (verify only): `onecx_pipecat/config.py`, `onecx_pipecat/models.py`, `onecx_pipecat/adapters/*.py`, `onecx_pipecat/adapters/factory.py`, `onecx_pipecat/container.py`

**Interfaces:**
- Consumes: `onecx_pipecat.config.Settings` and the six protocols exported from `onecx_pipecat.adapters` (`AuthAdapter`, `AgentConfigAdapter`, `SttAdapter`/`TtsAdapter`, `ConversationPersistence`, `PermissionAdapter`, `McpAdapter`).
- Produces: confirmation that each of the six required capabilities has a `Protocol` interface and an in-memory implementation, and that typed nested settings exist.

- [ ] **Step 1: Confirm the six protocols are importable and the factory builds all six**

Run:
```bash
export PATH="/home/runner/.local/bin:$PATH"
uv run --python 3.12 python -c "
from onecx_pipecat.adapters import (AuthAdapter, AgentConfigAdapter, SttAdapter,
    TtsAdapter, ConversationPersistence, PermissionAdapter, McpAdapter)
from onecx_pipecat.config import Settings
from onecx_pipecat.container import AppContainer
c = AppContainer(Settings())
s = c.adapters()
assert set(s.__dict__) == {'auth','agent_config','stt','tts','persistence','permission','mcp'}, s
print('adapters:', s)
"
```
Expected: prints the `AdapterSummary` with all seven fields set to the `InMemory*` class names and exits 0.

- [ ] **Step 2: Confirm typed nested configuration with env overrides**

Run:
```bash
uv run --python 3.12 python -c "
import os
os.environ['ONECX_AUTH__ISSUER']='https://other'
os.environ['ONECX_PORT']='9000'
from onecx_pipecat.config import Settings
s = Settings(_env_file=None)
assert s.auth.issuer=='https://other' and s.port==9000 and s.speech.sample_rate_hz==16000
print('config ok:', s.auth.issuer, s.port)
"
```
Expected: prints `config ok: https://other 9000` (nested `__` delimiter mapping works).

- [ ] **Step 3: No commit in the expected path**

Run: `git status --porcelain`
Expected: empty.

**Dependencies:** Task 1.

### Task 4: Verify CI runs tests and static checks without cloud credentials

**Files:**
- Read (verify only): `.github/workflows/ci.yml`, `uv.lock`

**Interfaces:**
- Consumes: the CI workflow definition.
- Produces: confirmation the workflow triggers on push/PR, runs the three local gates plus a docs job, and references no secrets or provider credentials.

- [ ] **Step 1: Confirm the workflow triggers and job structure**

Run: `grep -nE 'on:|push:|pull_request:|jobs:|runs-on:' .github/workflows/ci.yml`
Expected: `on:`, `push:` (branches `main, prototype`), `pull_request:`, and two jobs (`test-and-lint`, `docs`) on `ubuntu-latest`.

- [ ] **Step 2: Confirm no external cloud credentials are used**

Run: `grep -nEi 'secrets\.|_token|_key|aws_|azure|google|credentials' .github/workflows/ci.yml || echo "(none found)"`
Expected: `(none found)`.

- [ ] **Step 3: Confirm the workflow's local gates match what this plan ran**

Run: `grep -nE 'uv sync|ruff check|ruff format|pytest' .github/workflows/ci.yml`
Expected: `uv sync --python 3.12 --frozen`, `ruff check .`, `ruff format --check .`, `pytest -q` — identical to the commands in Task 1.

- [ ] **Step 4: No commit in the expected path**

Run: `git status --porcelain`
Expected: empty.

**Dependencies:** Task 1.

### Task 5: Verify Antora documentation covers setup, configuration, and adapter interfaces

**Files:**
- Read (verify only): `docs/antora.yml`, `docs/modules/ROOT/nav.adoc`, `docs/modules/ROOT/pages/{index,local-setup,configuration,adapter-interfaces}.adoc`, `antora-playbook.yml`

**Interfaces:**
- Consumes: the Antora module and site playbook.
- Produces: confirmation the four required pages exist and are wired into the nav, and (Node/npm permitting) that the module builds into a site whose index renders.

- [ ] **Step 1: Confirm all four documented pages exist and are in the nav**

Run:
```bash
ls docs/modules/ROOT/pages/
grep -nE 'index.adoc|local-setup.adoc|configuration.adoc|adapter-interfaces.adoc' docs/modules/ROOT/nav.adoc
```
Expected: `index.adoc`, `local-setup.adoc`, `configuration.adoc`, `adapter-interfaces.adoc` all present, and all four `xref:` lines present in `nav.adoc`.

- [ ] **Step 2: Confirm the Antora component and site playbook are coherent**

Run: `grep -nE 'name:|version:|start_page:' docs/antora.yml && grep -nE 'start_page:|start_path:' antora-playbook.yml`
Expected: component `name: onecx-pipecat`, `version: '0.0.1'`, `start_page: index.adoc`; playbook `start_page: onecx-pipecat:ROOT:index.adoc` and `start_path: docs`.

- [ ] **Step 3: Build the Antora site locally and smoke-check the rendered index (Node/npm present)**

Run:
```bash
export PATH="/home/runner/.local/bin:$PATH"
npm install -g antora@3.x
antora generate antora-playbook.yml
test -f ./build/site/index.html && grep -q "onecx-pipecat" ./build/site/index.html && echo DOCS_BUILD_OK
```
Expected: `DOCS_BUILD_OK` (this mirrors the `docs` job in `ci.yml` exactly). If `antora`/`npm` cannot be used in the execution environment, record that the docs-build criterion is enforced by CI and that the module structure (Steps 1–2) is complete and consistent.

- [ ] **Step 4: Clean the local Antora build artifacts**

Run: `rm -rf ./build ./antora-ui 2>/dev/null; git status --porcelain`
Expected: empty (`.gitignore` covers `.antora/`, `antora-ui/`, `build/`, `site/`; nothing tracked is removed).

**Dependencies:** Task 1.

### Task 6: Run the full CI-equivalent regression gate and close

**Files:**
- Read (verify only): all of the above.

**Interfaces:**
- Consumes: the whole application.
- Produces: a final all-green gate and the conclusion that #589 is complete.

- [ ] **Step 1: Run the complete local CI gate in one pass**

Run:
```bash
export PATH="/home/runner/.local/bin:$PATH"
uv sync --python 3.12 --frozen \
  && uv run --python 3.12 ruff check . \
  && uv run --python 3.12 ruff format --check . \
  && uv run --python 3.12 pytest -q
```
Expected: all four succeed; `pytest` reports `21 passed`.

- [ ] **Step 2: Confirm the working tree is clean**

Run: `git status --porcelain`
Expected: empty.

- [ ] **Step 3: State the outcome**

Expected: all acceptance criteria of #589 verified locally (install/run/test via `uv`; async health-path test under `pytest-asyncio`; six typed-config adapter interfaces; credential-free CI; Antora docs). The only step that runs solely in CI is the Antora `docs` job, which is mirrored by Task 5 Step 3. Close the issue as verified complete.

**Dependencies:** Tasks 1–5.

### Task 7: (Contingent) Fix and re-verify if any gate fails

**Files:**
- Modify (only if a Task 1–6 gate fails): the specific file named by the failing check.

**Interfaces:**
- Consumes: the failure output from the gate that failed.
- Produces: a minimal targeted fix that turns the failing gate green, then a full re-run of Task 6.

This task fires **only** if a check in Tasks 1–6 does not pass. Choose the single file and edit that the specific failure indicates, using the failing command's message as the source of truth. Concretely:

- **If `ruff check .` fails:** fix the exact lint rule violation reported at the reported file:line, keeping the code style identical to the surrounding module.
- **If `ruff format --check .` fails:** run `uv run --python 3.12 ruff format .` and review the produced diff to confirm it is whitespace/formatting only.
- **If `pytest -q` fails on a specific test:** inspect the assertion error and fix the module under `onecx_pipecat/` so the asserted externally-observable behavior holds. Do not weaken the test to make it pass.
- **If `uv sync --frozen` fails:** the lockfile or `pyproject.toml` is out of sync; regenerate with `uv lock` only if the pinned set genuinely cannot resolve, and re-check the diff is limited to the resolution.

After any edit:
- [ ] **Step 1: Re-run the full gate**

Run: the Task 6 Step 1 command block.
Expected: all green; `pytest -q` → `21 passed`.

- [ ] **Step 2: Re-run the affected acceptance check(s)**

Run: the specific failing task's verification command(s).
Expected: pass.

- [ ] **Step 3: Commit the fix**

Run:
```bash
git add -A
git commit -m "fix: resolve #589 gate failure (<one-line cause>)

Co-Authored-By: Claude <noreply@anthropic.com>"
```
Expected: one commit containing only the targeted fix; `git status --porcelain` empty afterward.

**Dependencies:** Whichever of Tasks 1–6 failed.

## Verification Steps

Run these to confirm the implementation is correct (all are the exact CI commands plus the two locally-runnable criteria):

1. `export PATH="/home/runner/.local/bin:$PATH" && uv sync --python 3.12 --frozen` — exit 0.
2. `uv run --python 3.12 ruff check .` — `All checks passed!`
3. `uv run --python 3.12 ruff format --check .` — `22 files already formatted.`
4. `uv run --python 3.12 pytest -q` — `21 passed`, banner shows `asyncio: mode=Mode.AUTO`.
5. `uv run --python 3.12 pytest tests/test_app.py::test_healthz_returns_ok_with_adapter_summary -v` — `PASSED` (async health-path test).
6. Boot the server and hit the health path (Task 2): `GET /healthz` → 200 with `status=OK` and the seven `InMemory*` adapter names; `GET /does-not-exist` → 404.
7. Confirm no credentials in CI: `grep -nEi 'secrets\.|_token|_key|aws_|azure|google|credentials' .github/workflows/ci.yml` → no matches.
8. Confirm the four Antora pages exist and are in the nav (Task 5 Step 1); build with `antora generate antora-playbook.yml` and check `./build/site/index.html` contains `onecx-pipecat` (Node/npm present).
9. `git status --porcelain` — empty.

All nine are expected to pass with no code changes; if any fail, execute Task 7.

## Notes

- **The work is already done and committed.** `ada4fd4` added the entire foundation (31 files) and `310ec68` added `tests/test_factory.py` and `tests/test_main.py`. This plan deliberately avoids re-authoring any of it. If a fresh, unrelated branch is expected upstream and this branch's commits are not yet merged, the "implementation" is the existing commits — the implementer should surface that to the parent issue #587 rather than duplicate the work.
- **CI-only check:** the Antora `docs` job runs only in GitHub Actions. It is mirrored locally in Task 5 Step 3 using the installed `antora@3.x` + Node v24 / npm 11.19; if the execution environment cannot install Antora, the docs-build criterion remains covered by CI and the module-structure checks (Task 5 Steps 1–2) still hold.
- **Port hygiene:** Task 2 uses port `8099` (not `8080`) to avoid clashing with any locally running instance; change it if busy.
- **Locked `pipecat-ai` resolves to 1.8.1** (within the `>=1.0.0,<2.0.0` pin); `uv run python -c "from importlib import metadata; print(metadata.version('pipecat-ai'))"` prints it. `/healthz` reports it and the test only asserts it is non-empty.
- **`--frozen` matters:** always sync with `--frozen` so the verified, locked dependency set is used; a non-frozen sync could pull a different `pipecat-ai`/`fastapi` patch and shift behavior.
- **Out of scope (per parent #587 boundary):** real cloud adapters, actual voice-session turn logic (beyond the prototype state vocabulary in `prototypes/voice-turn-sequence-prototype.html`), and session endpoints. The foundation ships in-memory adapters and a health path only; wiring a real voice loop is follow-up work, not part of #589.
- **Do not commit `build/`, `antora-ui/`, or venvs:** `.gitignore` already excludes them; Task 5 Step 4 removes any local build artifacts.
