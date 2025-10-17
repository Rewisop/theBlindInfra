"""Rendering helpers for markdown reports and dashboards."""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

import pandas as pd

from .config import DashboardConfig, project_path
from .schema import GpuPrice
from .util import log


def generate_report(prices: Iterable[GpuPrice], history_path: Optional[Path] = None) -> str:
    prices = list(prices)
    df = pd.DataFrame([p.model_dump() for p in prices])
    summary_lines = ["# GPU Market Daily Report", ""]
    generated_at = datetime.utcnow().isoformat()
    summary_lines.append(f"Generated at: `{generated_at}`\n")
    summary_lines.append(f"Total providers: **{df['provider_id'].nunique() if not df.empty else 0}**")
    summary_lines.append(f"Total offers: **{len(df)}**\n")

    if not df.empty:
        cheapest = df.sort_values("usd_per_hour").groupby("gpu", as_index=False).first()
        summary_lines.append("## Cheapest per GPU\n")
        summary_lines.append(cheapest[["gpu", "usd_per_hour", "provider_id", "region", "sku"]].to_markdown(index=False))
        summary_lines.append("")

        previous = _load_previous_snapshot(history_path)
        if previous is not None and previous:
            prev_df = pd.DataFrame(previous)
            movers = _compute_movers(prev_df, df)
            if not movers.empty:
                summary_lines.append("## Top Movers vs Previous\n")
                summary_lines.append(movers.to_markdown(index=False))
                summary_lines.append("")

        coverage = df.groupby("provider_id").size().reset_index(name="offers")
        summary_lines.append("## Provider Coverage\n")
        summary_lines.append(coverage.to_markdown(index=False))
        summary_lines.append("")

    if history_path and history_path.exists():
        changelog = _load_changelog(history_path)
        if changelog:
            summary_lines.append("## Recent Runs\n")
            summary_lines.extend(changelog)

    return "\n".join(summary_lines).strip() + "\n"


def _compute_movers(prev_df: pd.DataFrame, current_df: pd.DataFrame) -> pd.DataFrame:
    prev_cheapest = prev_df.sort_values("usd_per_hour").groupby("gpu", as_index=False).first()
    curr_cheapest = current_df.sort_values("usd_per_hour").groupby("gpu", as_index=False).first()
    merged = curr_cheapest.merge(prev_cheapest[["gpu", "usd_per_hour"]], on="gpu", how="left", suffixes=("_current", "_previous"))
    merged["delta"] = merged["usd_per_hour_current"] - merged["usd_per_hour_previous"]
    merged = merged.sort_values("delta")
    merged = merged.rename(columns={"usd_per_hour_current": "usd_per_hour", "usd_per_hour_previous": "prev_usd_per_hour"})
    return merged[["gpu", "usd_per_hour", "prev_usd_per_hour", "delta"]].head(10)


def _load_previous_snapshot(history_path: Optional[Path]) -> Optional[List[dict]]:
    if not history_path or not history_path.exists():
        return None
    try:
        lines = history_path.read_text(encoding="utf-8").strip().splitlines()
    except OSError:
        return None
    if len(lines) < 2:
        return None
    try:
        prev = json.loads(lines[-2])
    except json.JSONDecodeError:
        return None
    return prev.get("records")


def _load_changelog(history_path: Path) -> List[str]:
    try:
        lines = history_path.read_text(encoding="utf-8").strip().splitlines()
    except OSError:
        return []
    entries = []
    for line in lines[-5:]:
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = data.get("generated_at")
        offers = len(data.get("records", []))
        entries.append(f"- `{ts}` — {offers} offers")
    return entries


def generate_dashboard(prices: Iterable[GpuPrice], dashboard: DashboardConfig) -> dict[str, str]:
    prices = list(prices)
    data_path = project_path("data", "gpu_prices.json")
    html = f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <title>{dashboard.title}</title>
  <link rel=\"stylesheet\" href=\"assets/styles.css\" />
</head>
<body>
  <main>
    <h1>{dashboard.title}</h1>
    <p>{dashboard.intro}</p>
    <div id=\"summary\"></div>
    <div id=\"table\"></div>
    <div id=\"chart\"></div>
  </main>
  <script>
    window.DASHBOARD_CONFIG = {json.dumps({"sections": dashboard.sections})};
  </script>
  <script src=\"assets/app.js\"></script>
</body>
</html>
"""
    css = """
body { font-family: system-ui, sans-serif; margin: 2rem; background: #0f172a; color: #e2e8f0; }
main { max-width: 1000px; margin: 0 auto; }
table { width: 100%; border-collapse: collapse; margin-bottom: 1.5rem; }
th, td { border: 1px solid #1e293b; padding: 0.5rem; }
th { background: #1e293b; }
input, select { padding: 0.5rem; margin-right: 1rem; }
section { margin-bottom: 2rem; }
"""
    js = f"""async function loadData() {{
  const response = await fetch('../data/gpu_prices.json?_={datetime.utcnow().timestamp()}');
  const data = await response.json();
  return data;
}}

function renderSummary(prices) {{
  const container = document.getElementById('summary');
  const offers = prices.length;
  const providers = new Set(prices.map(p => p.provider_id)).size;
  container.innerHTML = `<section><h2>Snapshot</h2><p>${{offers}} offers across ${{providers}} providers.</p></section>`;
}}

function renderTable(prices) {{
  const container = document.getElementById('table');
  const providers = [...new Set(prices.map(p => p.provider_id))];
  container.innerHTML = `
  <section>
    <h2>Offers</h2>
    <label>Filter GPU <input id="gpu-filter" placeholder="e.g. A100" /></label>
    <label>Provider <select id="provider-filter"><option value="">All</option>${providers.map(p => `<option>${p}</option>`).join('')}</select></label>
    <table>
      <thead><tr><th>GPU</th><th>USD/hr</th><th>Provider</th><th>Region</th><th>SKU</th></tr></thead>
      <tbody></tbody>
    </table>
  </section>`;
  const tbody = container.querySelector('tbody');
  function applyFilters() {{
    const gpu = document.getElementById('gpu-filter').value.toLowerCase();
    const provider = document.getElementById('provider-filter').value;
    tbody.innerHTML = prices
      .filter(p => (!gpu || p.gpu.toLowerCase().includes(gpu)) && (!provider || p.provider_id === provider))
      .map(p => `<tr><td>${p.gpu}</td><td>${p.usd_per_hour.toFixed(4)}</td><td>${p.provider_id}</td><td>${p.region || ''}</td><td>${p.sku || ''}</td></tr>`)
      .join('');
  }}
  document.getElementById('gpu-filter').addEventListener('input', applyFilters);
  document.getElementById('provider-filter').addEventListener('change', applyFilters);
  applyFilters();
}}

function renderChart(prices) {{
  const container = document.getElementById('chart');
  const cheapest = Object.values(prices.reduce((acc, offer) => {{
    if (!acc[offer.gpu] || acc[offer.gpu].usd_per_hour > offer.usd_per_hour) {{
      acc[offer.gpu] = offer;
    }}
    return acc;
  }}, {{}}));
  cheapest.sort((a, b) => a.usd_per_hour - b.usd_per_hour);
  container.innerHTML = `<section><h2>Min $/hr by GPU</h2><div class="chart"></div></section>`;
  const chart = container.querySelector('.chart');
  chart.style.display = 'grid';
  chart.style.gap = '0.5rem';
  cheapest.forEach(item => {{
    const row = document.createElement('div');
    const label = document.createElement('div');
    label.textContent = `${{item.gpu}} (${{item.provider_id}})`;
    const bar = document.createElement('div');
    bar.style.height = '16px';
    bar.style.background = '#38bdf8';
    bar.style.width = `${{Math.max(item.usd_per_hour * 40, 5)}}px`;
    const value = document.createElement('span');
    value.textContent = `$${{item.usd_per_hour.toFixed(4)}}/hr`;
    value.style.marginLeft = '0.5rem';
    const wrapper = document.createElement('div');
    wrapper.style.display = 'flex';
    wrapper.style.alignItems = 'center';
    wrapper.appendChild(bar);
    wrapper.appendChild(value);
    row.appendChild(label);
    row.appendChild(wrapper);
    row.style.display = 'grid';
    row.style.gridTemplateColumns = '200px 1fr';
    chart.appendChild(row);
  }});
}}

(async function init() {{
  try {{
    const prices = await loadData();
    renderSummary(prices);
    renderTable(prices);
    renderChart(prices);
  }} catch (error) {{
    console.error('Failed to load dashboard data', error);
  }}
}})();
"""
    return {
        "index.html": html,
        "assets/app.js": js,
        "assets/styles.css": css,
    }


__all__ = ["generate_report", "generate_dashboard"]
