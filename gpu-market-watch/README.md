# GPU Market Watch

GPU Market Watch tracks public GPU hourly pricing across multiple infrastructure providers. It fetches
normalized pricing feeds, renders human friendly reports, and publishes a lightweight static dashboard
suitable for GitHub Pages.

## Features

- Python 3.11 compatible implementation.
- Declarative provider configuration via YAML.
- Deterministic, idempotent data pipeline: writes only when content changes.
- Resilient HTTP client with retries, timeout, and defensive parsing.
- Canonical schema enforced with Pydantic models and merge logic.
- Outputs JSON, CSV, JSONL history, Markdown report, and HTML dashboard artifacts.
- Daily GitHub Action workflow that only commits on diff.

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m marketwatch.cli
```

Artifacts will be written under `data/`, `reports/`, and `docs/`.

## Configuration

Configuration files live under `config/`:

- `settings.yaml`: HTTP and runtime defaults (timeouts, retries, history writing).
- `providers.yaml`: enabled providers and module entry points.
- `dashboard.yaml`: dashboard sections and labels.

Override settings via environment variables where applicable:

- `DEEP_MARKET_LOG_LEVEL`: change logging level (`INFO`, `DEBUG`, `WARN`).
- `HTTP_PROXY` / `HTTPS_PROXY`: configure outbound proxy for requests.

### Adding a provider

1. Create a new module in `marketwatch/providers/` that exposes a `fetch(session, cfg, now)` function returning
   normalized `GpuPrice` objects.
2. Add the provider to `config/providers.yaml` with its module path and configuration.
3. Run `python -m marketwatch.cli` to verify the integration and regenerate artifacts.

Always prefer official API endpoints; avoid scraping if terms prohibit it. Respect robots.txt, throttle requests,
and disable any provider upon request from the vendor.

## Tests

Run tests with:

```bash
pytest
```

## Publishing

Enable GitHub Pages from the repository settings by selecting the `main` branch and `/docs` folder.
The daily GitHub Action workflow (`.github/workflows/daily.yml`) runs the collector, commits changes via a token,
and pushes the refreshed dataset.

## Troubleshooting

- **No output changes**: The run is deterministic; if pricing feeds are unchanged, no artifacts are rewritten.
- **HTTP errors**: The client retries on transient failures. Review logs under the action run for details.
- **Provider failures**: Modules return partial data; a failure in one provider does not prevent other data from being collected.

## Ethics & Terms of Service

GPU Market Watch only uses public APIs or documentation designed for automated access. If a provider does not offer
an official feed, the integration falls back to courteous HTML parsing with conservative timeouts and structure checks.
We identify our client with a custom User-Agent and honor removal requests immediately.

## Post-setup checklist

- [ ] Add a `REPO_PAT` secret with `contents: write` scope for the automation workflow.
- [ ] Enable GitHub Pages (Settings → Pages → branch: `main`, folder: `/docs`).
- [ ] Trigger the **GPU Market Daily** workflow manually via *Run workflow* to produce the first dataset.

