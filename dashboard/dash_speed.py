#!/usr/bin/env python3
"""
SIGMON // Network Speed Monitor - Advanced Edition
Features: caching, alerts, health score, anomaly detection, compare mode,
ISP context, mobile responsive, tabbed layout.
"""
import dash
from dash import dcc, html, Input, Output, State, callback_context
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import os
import numpy as np
from datetime import datetime, timedelta
from functools import lru_cache
import json

# ------------------------------ Configuration --------------------------------
LOG_DIR = "/home/troggoman/speedtests/logs"
CACHE_TTL = 120  # seconds

# Design tokens
BG_PAGE      = "#0a0c0f"
BG_PANEL     = "#0f1318"
BG_PANEL2    = "#131920"
BORDER       = "#1e2a35"
ACCENT_AMBER = "#f0a500"
ACCENT_GREEN = "#39d98a"
ACCENT_BLUE  = "#3fa9f5"
ACCENT_RED   = "#f05454"
ACCENT_PURPLE= "#a78bfa"
TEXT_PRIMARY = "#e8edf2"
TEXT_MUTED   = "#b6bfc5"
TEXT_DIM     = "#3ec569"
FONT_MONO    = "'JetBrains Mono', 'Fira Code', 'Courier New', monospace"
FONT_UI      = "'DM Sans', 'Helvetica Neue', sans-serif"

PLOTLY_THEME = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family=FONT_MONO, color=TEXT_MUTED, size=11),
    xaxis=dict(gridcolor=BG_PANEL2, linecolor=BORDER, tickcolor=TEXT_DIM, zeroline=False),
    yaxis=dict(gridcolor=BG_PANEL2, linecolor=BORDER, tickcolor=TEXT_DIM, zeroline=False),
    legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor=BORDER, borderwidth=1),
    margin=dict(l=48, r=16, t=16, b=40),
    hovermode="x unified",
)

# ------------------------------ Data Helpers --------------------------------
@lru_cache(maxsize=1)
def load_all_csvs():
    """Load all CSV files once per TTL, return dict of DataFrames."""
    dfs = {}
    for name in ["ookla", "fast", "iperf3", "ndt7", "curl", "ping", "dns", "mtr"]:
        path = os.path.join(LOG_DIR, f"{name}.csv")
        try:
            df = pd.read_csv(path, on_bad_lines="skip")
            if "timestamp" in df.columns and not df.empty:
                df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
                df = df.dropna(subset=["timestamp"]).sort_values("timestamp")
                dfs[name] = df
        except Exception:
            pass
    return dfs

def get_filtered_data(df, hours):
    """Return df limited to last `hours` hours."""
    if df is None or df.empty:
        return df
    cutoff = datetime.now() - timedelta(hours=hours)
    return df[df["timestamp"] > cutoff]

def latest_val(df, col):
    if df is None or col not in df.columns or df.empty:
        return None
    vals = df[col].dropna()
    return vals.iloc[-1] if not vals.empty else None

def avg_val(df, col, hours=24):
    if df is None or col not in df.columns or df.empty:
        return None
    cutoff = datetime.now() - timedelta(hours=hours)
    recent = df[df["timestamp"] > cutoff][col].dropna()
    return recent.mean() if not recent.empty else None

def success_rate(df, hours=24):
    if df is None or "status" not in df.columns or df.empty:
        return None
    cutoff = datetime.now() - timedelta(hours=hours)
    recent = df[df["timestamp"] > cutoff]
    return (recent["status"] == "success").mean() * 100 if not recent.empty else None

def fmt(val, decimals=1, suffix=""):
    return "—" if val is None else f"{val:.{decimals}f}{suffix}"

def make_fig():
    fig = go.Figure()
    fig.update_layout(**PLOTLY_THEME)
    return fig

def add_anomaly_band(fig, df, col, color, hours_back=168):
    """Add rolling median line and shaded ±2σ band for anomaly detection."""
    if df is None or col not in df.columns or df.empty:
        return
    d = df[["timestamp", col]].dropna().sort_values("timestamp")
    if len(d) < 10:
        return
    d = d.set_index("timestamp")
    # Resample to hourly medians for stability
    hourly = d.resample("1H").median()
    rolling_median = hourly[col].rolling(window=24, min_periods=6).median()
    rolling_std = hourly[col].rolling(window=24, min_periods=6).std()
    upper = rolling_median + 2 * rolling_std
    lower = rolling_median - 2 * rolling_std
    common_index = rolling_median.dropna().index

    fig.add_trace(go.Scatter(
        x=common_index, y=upper.loc[common_index],
        mode="lines", line=dict(width=0), showlegend=False,
        hoverinfo="skip"
    ))
    fig.add_trace(go.Scatter(
        x=common_index, y=lower.loc[common_index],
        mode="lines", fill="tonexty", fillcolor=f"rgba({_hex_to_rgba(color, 0.15)})",
        line=dict(width=0), showlegend=False, hoverinfo="skip"
    ))
    fig.add_trace(go.Scatter(
        x=common_index, y=rolling_median.loc[common_index],
        mode="lines", name=f"{col} (24h median)",
        line=dict(color=color, width=1, dash="dot"),
        hoverinfo="skip"
    ))

def _hex_to_rgba(hex_color, alpha):
    hex_color = hex_color.lstrip('#')
    r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    return f"{r},{g},{b},{alpha}"

# ------------------------------ UI Components ------------------------------
def stat_card(label, value, unit="", accent=ACCENT_AMBER, sub=None):
    return html.Div([
        html.Div(label, className="stat-label"),
        html.Div([
            html.Span(value, className="stat-value", style={"color": accent}),
            html.Span(f" {unit}", className="stat-unit") if unit else None,
        ]),
        html.Div(sub, className="stat-sub") if sub else None,
    ], className="stat-card", style={"borderLeftColor": accent})

def mini_stat(label, value, unit="", accent=ACCENT_AMBER):
    return html.Div([
        html.Div(label, className="mini-label"),
        html.Span(value, className="mini-value", style={"color": accent}),
        html.Span(f" {unit}", className="mini-unit") if unit else None,
    ], className="mini-stat")

def section_header(title, tag=None):
    return html.Div([
        html.Span("▸ ", style={"color": ACCENT_AMBER}),
        html.Span(title, className="section-title"),
        html.Span(f"  [{tag}]", className="section-tag") if tag else None,
    ], className="section-header")

def chart_panel(children, style_extra=None):
    return html.Div(children, className="chart-panel", style=style_extra or {})

# ------------------------------ Alert Badges ------------------------------
def generate_alert_badges(dfs):
    """Return list of dbc.Badge components indicating issues."""
    badges = []
    # Ookla download degradation (>20% below 24h avg)
    ookla = dfs.get("ookla")
    if ookla is not None:
        latest_dl = latest_val(ookla, "download_mbps")
        avg_dl_24 = avg_val(ookla, "download_mbps", 24)
        if latest_dl and avg_dl_24 and latest_dl < avg_dl_24 * 0.8:
            badges.append(dbc.Badge("DL degraded", color="danger", className="me-1"))
        # Success rate < 90%
        sr = success_rate(ookla, 24)
        if sr is not None and sr < 90:
            badges.append(dbc.Badge(f"Success {sr:.0f}%", color="warning", className="me-1"))

    # Bufferbloat > 100ms
    fast = dfs.get("fast")
    if fast is not None:
        bloat = latest_val(fast, "bufferbloat_ms")
        if bloat and bloat > 100:
            badges.append(dbc.Badge("Bufferbloat >100ms", color="danger", className="me-1"))

    # Packet loss on Cloudflare ping > 1%
    ping = dfs.get("ping")
    if ping is not None:
        cf = ping[ping["host_label"] == "Cloudflare-DNS-JHB"] if "host_label" in ping.columns else pd.DataFrame()
        if not cf.empty:
            loss = latest_val(cf, "packet_loss_pct")
            if loss and loss > 1.0:
                badges.append(dbc.Badge("CF loss >1%", color="warning", className="me-1"))

    return badges

# ------------------------------ Health Score ------------------------------
def compute_health_score(dfs):
    """Return a score 0-100 based on weighted metrics."""
    score = 100
    ookla = dfs.get("ookla")
    if ookla is not None:
        dl = latest_val(ookla, "download_mbps")
        avg_dl = avg_val(ookla, "download_mbps", 24)
        if dl and avg_dl:
            ratio = dl / avg_dl
            if ratio < 0.5:
                score -= 20
            elif ratio < 0.8:
                score -= 10
        sr = success_rate(ookla, 24)
        if sr is not None:
            if sr < 80:
                score -= 20
            elif sr < 95:
                score -= 10
    fast = dfs.get("fast")
    if fast is not None:
        bloat = latest_val(fast, "bufferbloat_ms")
        if bloat:
            if bloat > 200:
                score -= 15
            elif bloat > 100:
                score -= 8
    ping = dfs.get("ping")
    if ping is not None:
        cf = ping[ping["host_label"] == "Cloudflare-DNS-JHB"] if "host_label" in ping.columns else pd.DataFrame()
        if not cf.empty:
            loss = latest_val(cf, "packet_loss_pct")
            if loss:
                if loss > 5:
                    score -= 20
                elif loss > 1:
                    score -= 10
    return max(0, min(100, score))

def health_gauge(score):
    color = ACCENT_GREEN if score >= 80 else (ACCENT_AMBER if score >= 50 else ACCENT_RED)
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        number={"font": {"color": color, "size": 40, "family": FONT_MONO}},
        gauge={
            "axis": {"range": [0, 100], "tickcolor": TEXT_MUTED},
            "bar": {"color": color},
            "bgcolor": "rgba(0,0,0,0)",
            "borderwidth": 0,
            "steps": [
                {"range": [0, 50], "color": f"rgba({_hex_to_rgba(ACCENT_RED, 0.2)})"},
                {"range": [50, 80], "color": f"rgba({_hex_to_rgba(ACCENT_AMBER, 0.2)})"},
                {"range": [80, 100], "color": f"rgba({_hex_to_rgba(ACCENT_GREEN, 0.2)})"},
            ],
        }
    ))
    fig.update_layout(height=150, margin=dict(l=20, r=20, t=30, b=10))
    return fig

# ------------------------------ App Initialization ------------------------------
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.DARKLY], title="SIGMON // Advanced")
server = app.server

# Custom CSS for mobile and styling
app.index_string = '''
<!DOCTYPE html>
<html>
<head>
    {%metas%}
    <title>{%title%}</title>
    {%favicon%}
    {%css%}
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=DM+Sans:wght@400;500&display=swap" rel="stylesheet">
    <style>
        body { background: #0a0c0f; color: #e8edf2; font-family: 'DM Sans', sans-serif; }
        .stat-card { background: #0f1318; border: 1px solid #1e2a35; border-left: 3px solid; padding: 14px 16px; flex: 1; min-width: 120px; }
        .stat-label { font-family: 'JetBrains Mono'; font-size: 10px; color: #b6bfc5; letter-spacing: 0.12em; text-transform: uppercase; margin-bottom: 6px; }
        .stat-value { font-family: 'JetBrains Mono'; font-size: 22px; font-weight: 600; letter-spacing: -0.02em; }
        .stat-unit { font-family: 'JetBrains Mono'; font-size: 11px; color: #b6bfc5; margin-left: 2px; }
        .stat-sub { font-family: 'JetBrains Mono'; font-size: 10px; color: #3ec569; margin-top: 3px; }
        .mini-stat { background: #131920; border: 1px solid #1e2a35; padding: 8px 12px; flex: 1; min-width: 80px; }
        .mini-label { font-family: 'JetBrains Mono'; font-size: 9px; color: #b6bfc5; letter-spacing: 0.1em; text-transform: uppercase; margin-bottom: 3px; }
        .mini-value { font-family: 'JetBrains Mono'; font-size: 14px; font-weight: 600; }
        .mini-unit { font-family: 'JetBrains Mono'; font-size: 10px; color: #b6bfc5; }
        .section-header { border-bottom: 1px solid #1e2a35; padding-bottom: 8px; margin-bottom: 12px; }
        .section-title { font-family: 'JetBrains Mono'; font-size: 11px; font-weight: 600; letter-spacing: 0.15em; text-transform: uppercase; color: #e8edf2; }
        .section-tag { font-family: 'JetBrains Mono'; font-size: 10px; color: #3ec569; margin-left: 8px; }
        .chart-panel { background: #0f1318; border: 1px solid #1e2a35; padding: 16px; margin-bottom: 2px; }
        .gap { height: 2px; }
        /* Mobile */
        @media (max-width: 768px) {
            .stat-card { min-width: 100%; margin-bottom: 2px; }
            .mini-stat { min-width: 45%; }
            .section-title { font-size: 10px; }
            .tab-content { padding: 10px 5px; }
        }
        .nav-tabs .nav-link { color: #b6bfc5; font-family: 'JetBrains Mono'; font-size: 11px; text-transform: uppercase; }
        .nav-tabs .nav-link.active { background: #1e2a35; color: #f0a500; border-color: #1e2a35; }
    </style>
</head>
<body>{%app_entry%}<footer>{%config%}{%scripts%}{%renderer%}</footer>
</body>
</html>
'''

# Layout
app.layout = dbc.Container([
    dcc.Interval(id="tick", interval=CACHE_TTL*1000),
    dcc.Store(id="cached-data", storage_type="memory"),

    # Header with alerts and clock
    dbc.Row([
        dbc.Col(html.Div([
            html.Span("SIGMON", style={"fontFamily": FONT_MONO, "fontSize": "18px", "fontWeight": "600", "color": ACCENT_AMBER, "letterSpacing": "0.2em"}),
            html.Span(" // ADVANCED NETWORK MONITOR", style={"fontFamily": FONT_MONO, "fontSize": "11px", "color": TEXT_MUTED, "marginLeft": "8px"}),
        ]), width="auto"),
        dbc.Col(html.Div(id="alert-badges", className="d-flex flex-wrap"), width="auto"),
        dbc.Col(html.Div([
            html.Span("● ", style={"color": ACCENT_GREEN, "fontSize": "10px"}),
            html.Span(id="header-time", style={"fontFamily": FONT_MONO, "fontSize": "11px", "color": TEXT_MUTED}),
        ], className="text-end"), width="auto"),
    ], className="g-0 align-items-center py-3 border-bottom", style={"borderColor": BORDER}),

    # Time range selector
    dbc.Row([
        dbc.Col([
            dbc.Label("Time Range", style={"color": TEXT_MUTED, "fontSize": "10px"}),
            dcc.Dropdown(
                id="time-range",
                options=[
                    {"label": "Last 24 Hours", "value": 24},
                    {"label": "Last 7 Days", "value": 168},
                    {"label": "Last 30 Days", "value": 720},
                ],
                value=24,
                clearable=False,
                style={"width": "180px", "color": "#000"}
            )
        ], width="auto", className="mt-2"),
        dbc.Col(html.Div(id="isp-info", className="mt-2"), width="auto"),
    ], className="g-2 mb-3"),

    # Tabs
    dcc.Tabs(id="main-tabs", value="overview", children=[
        dcc.Tab(label="Overview", value="overview", className="custom-tab", selected_className="custom-tab--selected"),
        dcc.Tab(label="Latency & Routing", value="latency", className="custom-tab", selected_className="custom-tab--selected"),
        dcc.Tab(label="ISP & Health", value="isp", className="custom-tab", selected_className="custom-tab--selected"),
    ], colors={"border": BORDER, "primary": ACCENT_AMBER, "background": BG_PANEL}),

    html.Div(id="tab-content", className="mt-3"),
], fluid=True, style={"backgroundColor": BG_PAGE, "minHeight": "100vh"})

# ------------------------------ Callbacks ------------------------------
@app.callback(
    Output("header-time", "children"),
    Output("cached-data", "data"),
    Input("tick", "n_intervals")
)
def update_clock_and_cache(n):
    now = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
    # Load all CSVs and convert to JSON serializable format
    dfs = load_all_csvs()
    # We can't store DataFrames directly; convert to dict of records with timestamp strings
    serializable = {}
    for name, df in dfs.items():
        if df is not None and not df.empty:
            df_copy = df.copy()
            df_copy["timestamp"] = df_copy["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%S")
            serializable[name] = df_copy.to_dict("records")
    return now, serializable

@app.callback(
    Output("alert-badges", "children"),
    Input("cached-data", "data")
)
def update_alerts(data):
    if not data:
        return []
    dfs = {name: pd.DataFrame(records) for name, records in data.items()}
    for df in dfs.values():
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
    return generate_alert_badges(dfs)

@app.callback(
    Output("isp-info", "children"),
    Input("cached-data", "data")
)
def update_isp_info(data):
    if not data or "ookla" not in data:
        return "ISP: —"
    ookla = pd.DataFrame(data["ookla"])
    if "isp" in ookla.columns and not ookla.empty:
        latest_isp = ookla.iloc[-1]["isp"]
        return html.Span(f"ISP: {latest_isp}", style={"fontFamily": FONT_MONO, "color": TEXT_MUTED})
    return "ISP: Unknown"

@app.callback(
    Output("tab-content", "children"),
    Input("main-tabs", "value"),
    Input("cached-data", "data"),
    Input("time-range", "value")
)
def render_tab(tab, data, hours):
    if not data:
        return html.Div("No data available.", style={"color": TEXT_MUTED})

    dfs = {name: pd.DataFrame(records) for name, records in data.items()}
    for df in dfs.values():
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])

    # Apply time filter
    filtered_dfs = {name: get_filtered_data(df, hours) for name, df in dfs.items()}

    if tab == "overview":
        return render_overview_tab(filtered_dfs, hours)
    elif tab == "latency":
        return render_latency_tab(filtered_dfs, hours)
    elif tab == "isp":
        return render_isp_tab(dfs, filtered_dfs, hours)  # pass full dfs for health score

def render_overview_tab(dfs, hours):
    ookla = dfs.get("ookla")
    fast = dfs.get("fast")
    ndt7 = dfs.get("ndt7")
    iperf = dfs.get("iperf3")
    curl = dfs.get("curl")

    # KPI cards
    dl_ookla = latest_val(ookla, "download_mbps")
    ul_ookla = latest_val(ookla, "upload_mbps")
    ping_ookla = latest_val(ookla, "ping_ms")
    dl_avg = avg_val(ookla, "download_mbps", 24)
    ul_avg = avg_val(ookla, "upload_mbps", 24)
    sr = success_rate(ookla, 24)

    kpi_row = dbc.Row([
        dbc.Col(stat_card("DOWNLOAD", fmt(dl_ookla), "Mbps", ACCENT_GREEN, sub=f"24h avg: {fmt(dl_avg)} Mbps")),
        dbc.Col(stat_card("UPLOAD", fmt(ul_ookla), "Mbps", ACCENT_BLUE, sub=f"24h avg: {fmt(ul_avg)} Mbps")),
        dbc.Col(stat_card("PING", fmt(ping_ookla), "ms", ACCENT_AMBER)),
        dbc.Col(stat_card("SUCCESS RATE", fmt(sr,0), "%", ACCENT_GREEN if (sr or 0)>=90 else ACCENT_RED)),
    ], className="g-1 mb-3")

    # Ookla graphs
    fig_ookla = make_fig()
    if ookla is not None:
        make_line(fig_ookla, ookla, "download_mbps", "Download", ACCENT_GREEN)
        make_line(fig_ookla, ookla, "upload_mbps", "Upload", ACCENT_BLUE)
        add_anomaly_band(fig_ookla, ookla, "download_mbps", ACCENT_GREEN, hours)
    fig_ookla.update_layout(yaxis_title="Mbps", height=220)

    fig_ookla_ping = make_fig()
    if ookla is not None:
        make_line(fig_ookla_ping, ookla, "ping_ms", "Ping", ACCENT_AMBER)
        add_anomaly_band(fig_ookla_ping, ookla, "ping_ms", ACCENT_AMBER, hours)
    fig_ookla_ping.update_layout(yaxis_title="ms", height=220)

    # Fast + NDT7
    fig_fast = make_fig()
    if fast is not None:
        make_line(fig_fast, fast, "download_mbps", "Download", ACCENT_GREEN)
        make_line(fig_fast, fast, "upload_mbps", "Upload", ACCENT_BLUE)
    fig_fast.update_layout(yaxis_title="Mbps", height=200)

    fig_ndt7 = make_fig()
    if ndt7 is not None:
        make_line(fig_ndt7, ndt7, "download_mbps", "Download", ACCENT_GREEN)
        make_line(fig_ndt7, ndt7, "upload_mbps", "Upload", ACCENT_BLUE)
    fig_ndt7.update_layout(yaxis_title="Mbps", height=200)

    # iPerf3
    fig_iperf = make_fig()
    if iperf is not None:
        make_line(fig_iperf, iperf, "download_mbps", "Download", ACCENT_GREEN)
        make_line(fig_iperf, iperf, "upload_mbps", "Upload", ACCENT_BLUE)
    fig_iperf.update_layout(yaxis_title="Mbps", height=180)

    # cURL light
    curl_light = make_fig()
    if curl is not None:
        targets = ["hetzner_fsn1", "hetzner_ash", "hetzner_hel1"]
        colors = [ACCENT_GREEN, ACCENT_BLUE, ACCENT_AMBER]
        for t, c in zip(targets, colors):
            tdf = curl[(curl["target_name"]==t) & (curl["file_size_mb"]<=200)]
            if not tdf.empty:
                make_line(curl_light, tdf, "download_mbps", t, c)
    curl_light.update_layout(yaxis_title="Mbps", height=200)

    return html.Div([
        kpi_row,
        chart_panel([section_header("Ookla Speedtest"), dcc.Graph(figure=fig_ookla)]),
        html.Div(className="gap"),
        dbc.Row([
            dbc.Col(chart_panel([section_header("Fast.com"), dcc.Graph(figure=fig_fast)])),
            dbc.Col(chart_panel([section_header("NDT7"), dcc.Graph(figure=fig_ndt7)])),
        ], className="g-1"),
        html.Div(className="gap"),
        chart_panel([section_header("iPerf3"), dcc.Graph(figure=fig_iperf)]),
        html.Div(className="gap"),
        chart_panel([section_header("cURL 100MB"), dcc.Graph(figure=curl_light)]),
    ])

def render_latency_tab(dfs, hours):
    ping = dfs.get("ping")
    dns = dfs.get("dns")
    mtr = dfs.get("mtr")

    # Ping
    ping_hosts = ["Cloudflare-DNS-JHB", "Google-DNS", "MLab-JHB", "JHB-Local"]
    colors = [ACCENT_GREEN, ACCENT_BLUE, ACCENT_AMBER, ACCENT_PURPLE]
    fig_ping_lat = make_fig()
    fig_ping_loss = make_fig()
    for host, col in zip(ping_hosts, colors):
        if ping is not None:
            hdf = ping[ping["host_label"]==host]
            make_line(fig_ping_lat, hdf, "avg_ms", host, col)
            make_line(fig_ping_loss, hdf, "packet_loss_pct", host, col)
    fig_ping_lat.update_layout(yaxis_title="ms", height=200)
    fig_ping_loss.update_layout(yaxis_title="% loss", height=200)

    # DNS
    dns_resolvers = ["Cloudflare", "Google", "Quad9"]
    fig_dns = make_fig()
    if dns is not None:
        for res, col in zip(dns_resolvers, colors):
            rdf = dns[dns["resolver"]==res]
            make_line(fig_dns, rdf, "lookup_ms", res, col)
    fig_dns.update_layout(yaxis_title="ms", height=180)

    # MTR (summary only; full hop would require additional data)
    fig_mtr = make_fig()
    if mtr is not None:
        labels = mtr["label"].unique()
        for lbl in labels:
            ldf = mtr[mtr["label"]==lbl]
            make_line(fig_mtr, ldf, "avg_ms", lbl, ACCENT_PURPLE)
    fig_mtr.update_layout(yaxis_title="ms", height=200)

    return html.Div([
        chart_panel([section_header("Ping Latency"), dcc.Graph(figure=fig_ping_lat)]),
        html.Div(className="gap"),
        chart_panel([section_header("Packet Loss"), dcc.Graph(figure=fig_ping_loss)]),
        html.Div(className="gap"),
        chart_panel([section_header("DNS Resolution"), dcc.Graph(figure=fig_dns)]),
        html.Div(className="gap"),
        chart_panel([section_header("MTR (Final Hop)"), dcc.Graph(figure=fig_mtr)]),
    ])

def render_isp_tab(full_dfs, filtered_dfs, hours):
    health_score = compute_health_score(full_dfs)
    gauge = health_gauge(health_score)

    # ISP info from Ookla
    ookla = full_dfs.get("ookla")
    isp_name = "Unknown"
    isp_as = ""
    if ookla is not None and "isp" in ookla.columns:
        latest = ookla.iloc[-1]
        isp_name = latest.get("isp", "Unknown")
        # AS not directly available, can be parsed if needed
    isp_card = stat_card("ISP", isp_name, "", ACCENT_BLUE)

    # Compare mode: date pickers and graph
    compare_card = html.Div([
        section_header("Compare Two Dates"),
        dbc.Row([
            dbc.Col(dcc.DatePickerSingle(id="date1", date=datetime.now().date()-timedelta(days=1), display_format="YYYY-MM-DD")),
            dbc.Col(dcc.DatePickerSingle(id="date2", date=datetime.now().date(), display_format="YYYY-MM-DD")),
        ], className="mb-2"),
        dcc.Graph(id="compare-graph", config={"displayModeBar": False}, style={"height": "250px"})
    ])

    return html.Div([
        dbc.Row([
            dbc.Col(isp_card, width=4),
            dbc.Col(dcc.Graph(figure=gauge, config={"displayModeBar": False}), width=8),
        ], className="g-1 mb-3"),
        chart_panel(compare_card),
    ])

# Additional callback for compare graph
@app.callback(
    Output("compare-graph", "figure"),
    Input("date1", "date"),
    Input("date2", "date"),
    Input("cached-data", "data")
)
def update_compare_graph(date1, date2, data):
    if not data or not date1 or not date2:
        return go.Figure()
    dfs = {name: pd.DataFrame(records) for name, records in data.items()}
    for df in dfs.values():
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
    ookla = dfs.get("ookla")
    if ookla is None:
        return go.Figure()

    date1 = pd.to_datetime(date1).date()
    date2 = pd.to_datetime(date2).date()
    d1 = ookla[ookla["timestamp"].dt.date == date1]
    d2 = ookla[ookla["timestamp"].dt.date == date2]

    fig = make_fig()
    make_line(fig, d1, "download_mbps", f"{date1} DL", ACCENT_GREEN)
    make_line(fig, d2, "download_mbps", f"{date2} DL", ACCENT_BLUE)
    fig.update_layout(yaxis_title="Mbps", height=250)
    return fig

# Helper to maintain make_line
def make_line(fig, df, col, name, color, dash="solid", mode="lines"):
    if df is None or col not in df.columns or df.empty:
        return
    d = df[["timestamp", col]].dropna()
    fig.add_trace(go.Scatter(
        x=d["timestamp"], y=d[col], name=name, mode=mode,
        line=dict(color=color, width=1.5, dash=dash),
    ))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=False)
