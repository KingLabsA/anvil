"""FastAPI dashboard with Plotly charts for agent telemetry data."""

from __future__ import annotations

import html
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

from agent_telemetry.error_tracker import detect_errors, generate_error_report
from agent_telemetry.models import Span
from agent_telemetry.storage import TelemetryStorage
from agent_telemetry.token_tracker import estimate_cost

app = FastAPI(title="AgentTelemetry", version="0.1.0")

_storage: Optional[TelemetryStorage] = None
_spans_cache: dict[str, list[Span]] = {}


def _plotly_cdn() -> str:
    return """<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>"""


def _base_html(title: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{html.escape(title)} — AgentTelemetry</title>
    <style>
        :root {{ --bg: #0f172a; --surface: #1e293b; --text: #e2e8f0; --accent: #38bdf8; --red: #f87171; --green: #4ade80; --yellow: #fbbf24; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 1rem; background: var(--bg); color: var(--text); }}
        a {{ color: var(--accent); text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        .card {{ background: var(--surface); border-radius: 0.5rem; padding: 1.25rem; margin-bottom: 1rem; }}
        h1, h2, h3 {{ margin-top: 0; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ text-align: left; padding: 0.5rem 0.75rem; border-bottom: 1px solid #334155; }}
        th {{ color: var(--accent); font-weight: 600; }}
        .metric {{ display: inline-block; background: var(--surface); border-radius: 0.5rem; padding: 1rem 1.5rem; margin: 0.25rem; min-width: 140px; }}
        .metric .value {{ font-size: 1.75rem; font-weight: 700; }}
        .metric .label {{ font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: #94a3b8; }}
        nav {{ margin-bottom: 1rem; }}
        nav a {{ margin-right: 1rem; }}
        .chart {{ width: 100%; height: 400px; }}
        .badge {{ display: inline-block; padding: 0.125rem 0.5rem; border-radius: 0.25rem; font-size: 0.75rem; font-weight: 600; }}
        .badge-ok {{ background: #166534; color: var(--green); }}
        .badge-error {{ background: #7f1d1d; color: var(--red); }}
        .badge-timeout {{ background: #78350f; color: var(--yellow); }}
    </style>
    {_plotly_cdn()}
</head>
<body>
    <nav>
        <a href="/dashboard">Dashboard</a>
        <a href="/cost/report">Cost Report</a>
        <a href="/errors/report">Error Report</a>
    </nav>
    {body}
</body>
</html>"""


def _init_storage() -> TelemetryStorage:
    global _storage
    if _storage is None:
        _storage = TelemetryStorage()
    return _storage


def _load_spans(session_id: str | None = None) -> list[Span]:
    storage = _init_storage()
    if session_id:
        if session_id in _spans_cache:
            return _spans_cache[session_id]
        spans = storage.query_spans(session_id=session_id, limit=100000)
        _spans_cache[session_id] = spans
        return spans
    return []


def _make_timeline_chart(spans: list[Span], div_id: str = "timeline") -> str:
    if not spans:
        return f'<div id="{div_id}"></div><p>No data.</p>'

    timestamps = [s.timestamp.isoformat() if s.timestamp else "" for s in spans]
    durations = [s.duration_ms for s in spans]
    tools = [s.tool_name for s in spans]
    colors = {"ok": "#4ade80", "error": "#f87171", "timeout": "#fbbf24"}
    bar_colors = [colors.get(s.status.value, "#94a3b8") for s in spans]

    return f"""
    <div id="{div_id}" class="chart"></div>
    <script>
    Plotly.newPlot('{div_id}', [{{
        x: {timestamps},
        y: {durations},
        type: 'bar',
        marker: {{ color: {bar_colors} }},
        text: {tools},
        hovertemplate: '%{{text}}<br>%{{y}} ms<extra></extra>'
    }}], {{
        title: 'Tool Call Timeline',
        xaxis: {{ title: 'Time' }},
        yaxis: {{ title: 'Duration (ms)', type: 'log' }},
        paper_bgcolor: '#0f172a',
        plot_bgcolor: '#1e293b',
        font: {{ color: '#e2e8f0' }},
        margin: {{ t: 40 }}
    }});
    </script>"""


def _make_heatmap_chart(spans: list[Span], div_id: str = "heatmap") -> str:
    if not spans:
        return f'<div id="{div_id}"></div><p>No data.</p>'

    tool_names: list[str] = sorted(set(s.tool_name for s in spans))
    hours: list[str] = sorted(set(
        (s.timestamp.strftime("%Y-%m-%d %H:00") if s.timestamp else "unknown")
        for s in spans
    ))

    z: list[list[int]] = []
    for tool in tool_names:
        row = []
        for hour in hours:
            count = sum(
                1 for s in spans
                if s.tool_name == tool
                and (s.timestamp.strftime("%Y-%m-%d %H:00") if s.timestamp else "unknown") == hour
            )
            row.append(count)
        z.append(row)

    return f"""
    <div id="{div_id}" class="chart"></div>
    <script>
    Plotly.newPlot('{div_id}', [{{
        z: {z},
        x: {hours},
        y: {tool_names},
        type: 'heatmap',
        colorscale: 'Viridis',
        hovertemplate: '%{{y}} at %{{x}}<br>%{{z}} calls<extra></extra>'
    }}], {{
        title: 'Tool Usage Heatmap',
        xaxis: {{ title: 'Time' }},
        yaxis: {{ title: 'Tool' }},
        paper_bgcolor: '#0f172a',
        plot_bgcolor: '#1e293b',
        font: {{ color: '#e2e8f0' }},
        margin: {{ t: 40 }}
    }});
    </script>"""


def _make_cost_chart(spans: list[Span], div_id: str = "cost_chart") -> str:
    if not spans:
        return f'<div id="{div_id}"></div><p>No data.</p>'

    by_tool: dict[str, float] = {}
    for s in spans:
        by_tool[s.tool_name] = by_tool.get(s.tool_name, 0.0) + s.cost_usd

    tools = list(by_tool.keys())
    costs = list(by_tool.values())

    return f"""
    <div id="{div_id}" class="chart"></div>
    <script>
    Plotly.newPlot('{div_id}', [{{
        labels: {tools},
        values: {costs},
        type: 'pie',
        hole: 0.4,
        textinfo: 'label+percent',
        textfont: {{ color: '#e2e8f0' }},
        marker: {{ colors: ['#38bdf8','#4ade80','#fbbf24','#f87171','#a78bfa','#fb923c','#2dd4bf','#e879f9'] }}
    }}], {{
        title: 'Cost by Tool',
        paper_bgcolor: '#0f172a',
        plot_bgcolor: '#1e293b',
        font: {{ color: '#e2e8f0' }},
        margin: {{ t: 40 }}
    }});
    </script>"""


def _make_error_chart(session_id: str, div_id: str = "error_chart") -> str:
    spans = _load_spans(session_id)
    errors = detect_errors(spans)

    by_type: dict[str, int] = {}
    for e in errors:
        by_type[e.error_type] = by_type.get(e.error_type, 0) + 1

    if not by_type:
        return f'<div id="{div_id}"></div><p>No errors found.</p>'

    types = list(by_type.keys())
    counts = list(by_type.values())

    return f"""
    <div id="{div_id}" class="chart"></div>
    <script>
    Plotly.newPlot('{div_id}', [{{
        x: {types},
        y: {counts},
        type: 'bar',
        marker: {{ color: '#f87171' }}
    }}], {{
        title: 'Errors by Type',
        xaxis: {{ title: 'Error Type' }},
        yaxis: {{ title: 'Count' }},
        paper_bgcolor: '#0f172a',
        plot_bgcolor: '#1e293b',
        font: {{ color: '#e2e8f0' }},
        margin: {{ t: 40 }}
    }});
    </script>"""


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    storage = _init_storage()
    sessions = storage.list_sessions()

    session_cards = ""
    for sid in sessions:
        metrics = storage.get_session_metrics(sid)
        if metrics:
            session_cards += f"""
            <div class="card">
                <h3><a href="/sessions/{sid}">{html.escape(sid)}</a></h3>
                <div class="metric"><div class="label">Tokens</div><div class="value">{metrics.total_tokens:,}</div></div>
                <div class="metric"><div class="label">Cost</div><div class="value">${metrics.total_cost:.4f}</div></div>
                <div class="metric"><div class="label">Tool Calls</div><div class="value">{metrics.tool_calls}</div></div>
                <div class="metric"><div class="label">Errors</div><div class="value">{metrics.error_count}</div></div>
                <div class="metric"><div class="label">Duration</div><div class="value">{metrics.duration_seconds:.1f}s</div></div>
            </div>"""

    if not session_cards:
        session_cards = '<div class="card"><p>No sessions found. Use <code>agenttelemetry analyze &lt;trace.jsonl&gt;</code> to ingest traces.</p></div>'

    body = f"""
    <h1>AgentTelemetry Dashboard</h1>
    {session_cards}
    """
    return HTMLResponse(_base_html("Dashboard", body))


@app.get("/sessions/{session_id}", response_class=HTMLResponse)
async def session_detail(request: Request, session_id: str):
    storage = _init_storage()
    metrics = storage.get_session_metrics(session_id)
    spans = _load_spans(session_id)

    if not metrics:
        body = f'<div class="card"><p>Session <code>{html.escape(session_id)}</code> not found.</p></div>'
        return HTMLResponse(_base_html("Session Not Found", body))

    spans_rows = ""
    for s in spans[:100]:
        badge_class = f"badge-{s.status.value}"
        spans_rows += f"""
        <tr>
            <td>{html.escape(s.tool_name)}</td>
            <td>{s.input_tokens:,}</td>
            <td>{s.output_tokens:,}</td>
            <td>{s.duration_ms:.0f}ms</td>
            <td>${s.cost_usd:.6f}</td>
            <td><span class="badge {badge_class}">{s.status.value}</span></td>
            <td>{html.escape(s.error or "")[:80]}</td>
        </tr>"""

    body = f"""
    <h1>Session: {html.escape(session_id)}</h1>
    <div class="card">
        <div class="metric"><div class="label">Total Tokens</div><div class="value">{metrics.total_tokens:,}</div></div>
        <div class="metric"><div class="label">Total Cost</div><div class="value">${metrics.total_cost:.4f}</div></div>
        <div class="metric"><div class="label">Tool Calls</div><div class="value">{metrics.tool_calls}</div></div>
        <div class="metric"><div class="label">Errors</div><div class="value">{metrics.error_count}</div></div>
        <div class="metric"><div class="label">Cache Hit Rate</div><div class="value">{metrics.cache_hit_rate:.1%}</div></div>
        <div class="metric"><div class="label">P50 Duration</div><div class="value">{metrics.p50_duration_ms:.0f}ms</div></div>
        <div class="metric"><div class="label">P95 Duration</div><div class="value">{metrics.p95_duration_ms:.0f}ms</div></div>
        <div class="metric"><div class="label">P99 Duration</div><div class="value">{metrics.p99_duration_ms:.0f}ms</div></div>
    </div>
    <div class="card">
        <h3>Tool Calls</h3>
        <table>
            <tr><th>Tool</th><th>Input</th><th>Output</th><th>Duration</th><th>Cost</th><th>Status</th><th>Error</th></tr>
            {spans_rows}
        </table>
    </div>
    <div class="card">
        <a href="/sessions/{session_id}/timeline">Timeline</a> |
        <a href="/sessions/{session_id}/heatmap">Heatmap</a> |
        <a href="/cost/report?session_id={session_id}">Cost Report</a>
    </div>
    """
    return HTMLResponse(_base_html(f"Session {session_id}", body))


@app.get("/sessions/{session_id}/timeline", response_class=HTMLResponse)
async def session_timeline(request: Request, session_id: str):
    spans = _load_spans(session_id)
    chart = _make_timeline_chart(spans)
    cost_chart = _make_cost_chart(spans)

    body = f"""
    <h1>Timeline: {html.escape(session_id)}</h1>
    <div class="card">{chart}</div>
    <div class="card">{cost_chart}</div>
    """
    return HTMLResponse(_base_html(f"Timeline — {session_id}", body))


@app.get("/sessions/{session_id}/heatmap", response_class=HTMLResponse)
async def session_heatmap(request: Request, session_id: str):
    spans = _load_spans(session_id)
    chart = _make_heatmap_chart(spans)

    body = f"""
    <h1>Heatmap: {html.escape(session_id)}</h1>
    <div class="card">{chart}</div>
    """
    return HTMLResponse(_base_html(f"Heatmap — {session_id}", body))


@app.get("/cost/report", response_class=HTMLResponse)
async def cost_report(request: Request, session_id: Optional[str] = None):
    storage = _init_storage()
    spans = _load_spans(session_id) if session_id else []

    if not spans:
        all_tools = storage.aggregate_tool_metrics()
        if not all_tools:
            body = '<div class="card"><p>No cost data available.</p></div>'
            return HTMLResponse(_base_html("Cost Report", body))

        rows = ""
        total_cost = 0.0
        for t in all_tools:
            total_cost += t.total_cost_usd
            rows += f"""
            <tr>
                <td>{html.escape(t.tool_name)}</td>
                <td>{t.call_count}</td>
                <td>${t.total_cost_usd:.6f}</td>
                <td>{t.total_input_tokens:,}</td>
                <td>{t.total_output_tokens:,}</td>
            </tr>"""

        body = f"""
        <h1>Cost Report — All Sessions</h1>
        <div class="card">
            <div class="metric"><div class="label">Total Cost</div><div class="value">${total_cost:.4f}</div></div>
        </div>
        <div class="card">
            <table>
                <tr><th>Tool</th><th>Calls</th><th>Cost</th><th>Input Tokens</th><th>Output Tokens</th></tr>
                {rows}
            </table>
        </div>
        """
        return HTMLResponse(_base_html("Cost Report", body))

    from agent_telemetry.models import CostReport as CR
    breakdown = estimate_cost(
        sum(s.input_tokens for s in spans),
        sum(s.output_tokens for s in spans),
        spans[0].model if spans else "unknown",
        sum(s.cache_read for s in spans),
        sum(s.cache_creation for s in spans),
    )
    report = CR(
        session_id=session_id or "all",
        input_cost=breakdown.input_cost,
        output_cost=breakdown.output_cost,
        cache_cost=breakdown.cache_cost,
        total_cost=breakdown.total_cost,
        model=breakdown.model,
        input_tokens=breakdown.input_tokens,
        output_tokens=breakdown.output_tokens,
        cache_read_tokens=breakdown.cache_read_tokens,
        cache_creation_tokens=breakdown.cache_creation_tokens,
        span_count=len(spans),
    )

    chart = _make_cost_chart(spans)

    body = f"""
    <h1>Cost Report — {html.escape(report.session_id)}</h1>
    <div class="card">
        <div class="metric"><div class="label">Input Cost</div><div class="value">${report.input_cost:.6f}</div></div>
        <div class="metric"><div class="label">Output Cost</div><div class="value">${report.output_cost:.6f}</div></div>
        <div class="metric"><div class="label">Cache Cost</div><div class="value">${report.cache_cost:.6f}</div></div>
        <div class="metric"><div class="label">Total Cost</div><div class="value">${report.total_cost:.6f}</div></div>
        <div class="metric"><div class="label">Model</div><div class="value">{html.escape(report.model)}</div></div>
        <div class="metric"><div class="label">Spans</div><div class="value">{report.span_count}</div></div>
    </div>
    <div class="card">{chart}</div>
    """
    return HTMLResponse(_base_html(f"Cost Report — {report.session_id}", body))


@app.get("/errors/report", response_class=HTMLResponse)
async def error_report(request: Request, session_id: Optional[str] = None):
    storage = _init_storage()
    sessions = [session_id] if session_id else storage.list_sessions()

    if not sessions:
        body = '<div class="card"><p>No error data available.</p></div>'
        return HTMLResponse(_base_html("Error Report", body))

    all_errors_section = ""
    for sid in sessions:
        report = generate_error_report(sid, spans=_load_spans(sid) or None)
        if report.total_errors == 0:
            continue

        error_rows = ""
        for e in report.errors[:50]:
            badge = "✓" if e.recovered else "✗"
            error_rows += f"""
            <tr>
                <td>{html.escape(e.error_type)}</td>
                <td>{html.escape(e.tool_name)}</td>
                <td>{html.escape(e.error_message[:100])}</td>
                <td>{badge}</td>
            </tr>"""

        chart = _make_error_chart(sid)

        all_errors_section += f"""
        <div class="card">
            <h3><a href="/sessions/{ sid}">{html.escape(sid)}</a></h3>
            <div class="metric"><div class="label">Total Errors</div><div class="value">{report.total_errors}</div></div>
            <div class="metric"><div class="label">Recovered</div><div class="value">{report.recovered_errors}</div></div>
            <div class="metric"><div class="label">Recovery Rate</div><div class="value">{report.recovery_rate:.0%}</div></div>
            <table>
                <tr><th>Type</th><th>Tool</th><th>Message</th><th>Recovered</th></tr>
                {error_rows}
            </table>
            {chart}
        </div>"""

    if not all_errors_section:
        all_errors_section = '<div class="card"><p>No errors found across sessions. 🎉</p></div>'

    body = f"""
    <h1>Error Report</h1>
    {all_errors_section}
    """
    return HTMLResponse(_base_html("Error Report", body))
