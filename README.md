# OneCX Pipecat

Foundation for authenticated voice sessions built on
[Pipecat](https://pipecat.ai). Every external dependency is a replaceable
adapter so the app runs, tests, and lints without any cloud credentials.

## Quick start

```bash
uv sync --python 3.12
uv run --python 3.12 pytest -q
uv run --python 3.12 uvicorn onecx_pipecat.main:app --port 8080
```

## Linting and pre-commit

```bash
uv run --python 3.11 ruff check .
chmod +x .githooks/pre-commit
git config core.hooksPath .githooks
```

## Container image and Helm chart

```bash
docker build -t onecx-pipecat .
docker run --rm -p 8080:8080 onecx-pipecat
helm dependency build helm && helm lint helm
```

See the Deployment page in the documentation for configuration, the Helm
chart and the CI workflows.

## Documentation

Antora module under `docs/` (component descriptor `docs/antora.yml`, site
playbook `antora-playbook.yml`). Local setup, the configuration reference,
and the adapter interfaces are documented there.

## Layout

- `onecx_pipecat/` — application package (`config`, `models`,
  `adapters`, `container`, `app`, `main`).
- `tests/` — `pytest` + `pytest-asyncio` tests (async by default via
  `asyncio_mode = "auto"`).
- `docs/` — Antora module.
- `prototypes/` — the throwaway HTML state-machine prototype that this
  foundation is grounded in.
- `.github/workflows/ci.yml` — CI (tests, lint, docs build, no credentials).
