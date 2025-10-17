"""CLI entry point for GPU Market Watch."""
from __future__ import annotations

import json
from pathlib import Path

from .config import load_dashboard, load_settings, project_path
from .providers.registry import get_enabled_providers
from .render import generate_dashboard, generate_report
from .schema import merge_records
from .util import (
    append_jsonl,
    log,
    make_session,
    utc_now,
    write_csv_atomic,
    write_json_atomic,
    write_text_atomic,
)


def run() -> None:
    settings = load_settings()
    now = utc_now()
    session = make_session()
    records = []
    for cfg, func in get_enabled_providers():
        try:
            fetched = func(session, cfg, now)
            log("INFO", f"{cfg.id}: fetched {len(fetched)} offers")
            records.extend(fetched)
        except Exception as exc:  # pragma: no cover - defensive
            log("ERROR", f"{cfg.id}: failed with {exc}")
            if settings.run.fail_on_any_error:
                raise
    merged = merge_records(records)
    json_path = project_path("data", "gpu_prices.json")
    csv_path = project_path("data", "gpu_prices.csv")
    history_path = project_path("data", "history.jsonl")
    report_path = project_path("reports", "README.md")
    dashboard_dir = project_path("docs")

    json_payload = [r.model_dump(mode="json") for r in merged]
    changed_json = write_json_atomic(json_path, json_payload)
    changed_csv = write_csv_atomic(csv_path, json_payload)

    if settings.run.write_history and changed_json:
        append_jsonl(
            history_path,
            {
                "generated_at": now.isoformat(),
                "records": json_payload,
            },
        )

    report = generate_report(merged, history_path)
    changed_report = write_text_atomic(report_path, report)

    dashboard_cfg = load_dashboard()
    dashboard_assets = generate_dashboard(merged, dashboard_cfg)
    changed_dashboard = False
    for relative, content in dashboard_assets.items():
        path = dashboard_dir / relative
        if write_text_atomic(path, content):
            changed_dashboard = True

    changed = changed_json or changed_csv or changed_report or changed_dashboard
    log("INFO", f"changed: {changed}")
    print(json.dumps({"changed": changed, "records": len(merged)}))


if __name__ == "__main__":
    run()
