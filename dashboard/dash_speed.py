#!/usr/bin/env python3
"""
SIGMON // Network Speed Monitor - Advanced Edition
Retains original dark terminal aesthetic; adds caching, alerts, health score,
anomaly bands, compare mode, ISP info, and tabbed navigation.
"""
import dash
from dash import dcc, html, Input, Output, State
import pandas as pd
import plotly.graph_objects as go
import os
from datetime import datetime, timedelta
import json
import dash_bootstrap_components as dbc

LOG_DIR = "/home/troggoman/speedtests/logs"

# ---------------------------------------------------------------------------
# Design tokens — exactly as original
# ---------------------------------------------------------------------------
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
    legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor=BORDER, borderwidth=1, font=dict(size=10)),
    margin=dict(l=48, r=16, t=16, b=40),
    hovermode="x unified",
    hoverlabel=dict(bgcolor=BG_PANEL2, bordercolor=BORDER,
                    font=dict(family=FONT_MONO, size=11, color=TEXT_PRIMARY)),
)

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def load_csv(filename):
    path = os.path.join(LOG_DIR, filename)
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_csv(path, on_bad_lines="skip")
        if "timestamp" not in df.columns or df.empty:
            return None
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df.dropna(subset=["timestamp"]).sort_values("timestamp")
        return df
    except Exception:
        return None

def get_filtered_data(df, hours):
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

def make_line(fig, df, col, name, color, dash="solid", mode="lines"):
    if df is None or col not in df.columns or df.empty:
        return
    d = df[["timestamp", col]].dropna()
    fig.add_trace(go.Scatter(
        x=d["timestamp"], y=d[col], name=name, mode=mode,
        line=dict(color=color, width=1.5, dash=dash),
        hovertemplate=f"%{{y:.1f}}<extra>{name}</extra>",
    ))

def add_anomaly_band(fig, df, col, color):
    """Add rolling median line and ±2σ band for anomaly detection."""
    if df is None or col not in df.columns or df.empty:
        return
    d = df[["timestamp", col]].dropna().sort_values("timestamp")
    if len(d) < 20:
        return
    d = d.set_index("timestamp")
    hourly = d.resample("1H").median()
    rolling_median = hourly[col].rolling(window=24, min_periods=6).median()
    rolling_std = hourly[col].rolling(window=24, min_periods=6).std()
    upper = rolling_median + 2 * rolling_std
    lower = rolling_median - 2 * rolling_std
    common_index = rolling_median.dropna().index

    if not common_index.empty:
        fig.add_trace(go.Scatter(
            x=common_index, y=upper.loc[common_index],
            mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"
        ))
        fig.add_trace(go.Scatter(
            x=common_index, y=lower.loc[common_index],
            mode="lines", fill="tonexty", fillcolor=f"rgba({_hex_to_rgba(color, 0.12)})",
            line=dict(width=0), showlegend=False, hoverinfo="skip"
        ))
        fig.add_trace(go.Scatter(
            x=common_index, y=rolling_median.loc[common_index],
            mode="lines", name=f"{col} 24h median",
            line=dict(color=color, width=1, dash="dot"), hoverinfo="skip"
        ))

def _hex_to_rgba(hex_color, alpha):
    hex_color = hex_color.lstrip('#')
    r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    return f"{r},{g},{b},{alpha}"

# ---------------------------------------------------------------------------
# UI components — exactly as original
# ---------------------------------------------------------------------------

def stat_card(label, value, unit="", accent=ACCENT_AMBER, sub=None):
    return html.Div([
        html.Div(label, style={
            "fontFamily": FONT_MONO, "fontSize": "10px", "color": TEXT_MUTED,
            "letterSpacing": "0.12em", "textTransform": "uppercase", "marginBottom": "6px",
        }),
        html.Div([
            html.Span(value, style={
                "fontFamily": FONT_MONO, "fontSize": "22px", "fontWeight": "600",
                "color": accent, "letterSpacing": "-0.02em",
            }),
            html.Span(f" {unit}", style={
                "fontFamily": FONT_MONO, "fontSize": "11px", "color": TEXT_MUTED, "marginLeft": "2px",
            }) if unit else None,
        ], style={"display": "flex", "alignItems": "baseline"}),
        html.Div(sub, style={
            "fontFamily": FONT_MONO, "fontSize": "10px", "color": TEXT_DIM, "marginTop": "3px",
        }) if sub else None,
    ], style={
        "backgroundColor": BG_PANEL, "border": f"1px solid {BORDER}",
        "borderLeft": f"3px solid {accent}", "padding": "14px 16px",
        "minWidth": "120px", "flex": "1",
    })

def mini_stat(label, value, unit="", accent=ACCENT_AMBER):
    return html.Div([
        html.Div(label, style={
            "fontFamily": FONT_MONO, "fontSize": "9px", "color": TEXT_MUTED,
            "letterSpacing": "0.1em", "textTransform": "uppercase", "marginBottom": "3px",
        }),
        html.Span(value, style={"fontFamily": FONT_MONO, "fontSize": "14px",
                                 "fontWeight": "600", "color": accent}),
        html.Span(f" {unit}", style={"fontFamily": FONT_MONO, "fontSize": "10px",
                                      "color": TEXT_MUTED}) if unit else None,
    ], style={
        "backgroundColor": BG_PANEL2, "border": f"1px solid {BORDER}",
        "padding": "8px 12px", "flex": "1", "minWidth": "80px",
    })

def section_header(title, tag=None):
    return html.Div([
        html.Span("▸ ", style={"color": ACCENT_AMBER, "fontFamily": FONT_MONO}),
        html.Span(title, style={
            "fontFamily": FONT_MONO, "fontSize": "11px", "fontWeight": "600",
            "letterSpacing": "0.15em", "textTransform": "uppercase", "color": TEXT_PRIMARY,
        }),
        html.Span(f"  [{tag}]", style={
            "fontFamily": FONT_MONO, "fontSize": "10px", "color": TEXT_DIM, "marginLeft": "8px",
        }) if tag else None,
    ], style={"borderBottom": f"1px solid {BORDER}", "paddingBottom": "8px", "marginBottom": "12px"})

def chart_panel(children, style_extra=None):
    s = {"backgroundColor": BG_PANEL, "border": f"1px solid {BORDER}",
         "padding": "16px", "marginBottom": "2px"}
    if style_extra:
        s.update(style_extra)
    return html.Div(children, style=s)

GAP = html.Div(style={"height": "2px"})

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = dash.Dash(__name__, title="SIGMON // Speed Monitor")
server = app.server

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
        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
        html, body { background: #0a0c0f; color: #e8edf2; font-family: 'DM Sans', sans-serif; }
        ::-webkit-scrollbar { width: 6px; background: #0a0c0f; }
        ::-webkit-scrollbar-thumb { background: #1e2a35; border-radius: 3px; }
        body::after {
            content: ''; position: fixed; inset: 0; pointer-events: none; z-index: 9999;
            background: repeating-linear-gradient(0deg, rgba(0,0,0,0.03) 0px,
                rgba(0,0,0,0.03) 1px, transparent 1px, transparent 3px);
        }
        @keyframes fadein { from { opacity:0; transform:translateY(6px); } to { opacity:1; transform:translateY(0); } }
        .panel { animation: fadein 0.35s ease both; }
        /* Tab styling matching monospace theme */
        .tab-container { display: flex; border-bottom: 1px solid #1e2a35; margin-bottom: 16px; }
        .tab {
            font-family: 'JetBrains Mono', monospace; font-size: 11px; font-weight: 600;
            letter-spacing: 0.15em; text-transform: uppercase; color: #b6bfc5;
            padding: 10px 20px; cursor: pointer; border-bottom: 2px solid transparent;
            transition: all 0.1s;
        }
        .tab:hover { color: #e8edf2; }
        .tab--selected { color: #f0a500; border-bottom-color: #f0a500; }
        /* Alert badge */
        .alert-badge {
            display: inline-block; font-family: 'JetBrains Mono'; font-size: 9px;
            background: #f05454; color: #fff; padding: 2px 6px; border-radius: 10px;
            margin-left: 8px; text-transform: uppercase; letter-spacing: 0.05em;
        }
        .alert-badge.warning { background: #f0a500; }
        /* Time range dropdown */
        .time-dropdown .Select-control { background: #0f1318; border-color: #1e2a35; }
        .time-dropdown .Select-value-label { color: #e8edf2 !important; }
        /* Mobile */
        @media (max-width: 768px) {
            .stat-card { min-width: 100%; margin-bottom: 2px; }
        }
    </style>
</head>
<body>{%app_entry%}<footer>{%config%}{%scripts%}{%renderer%}</footer>
</body>
</html>
'''

app.layout = html.Div([
    dcc.Interval(id="tick", interval=120_000, n_intervals=0),
    dcc.Store(id="cached-data", storage_type="memory"),

    # Header with alerts, time dropdown, ISP
    html.Div([
        html.Div([
            html.Span("SIGMON", style={"fontFamily": FONT_MONO, "fontSize": "18px",
                                        "fontWeight": "600", "color": ACCENT_AMBER, "letterSpacing": "0.2em"}),
            html.Span(" // NETWORK SPEED MONITOR", style={"fontFamily": FONT_MONO,
                "fontSize": "11px", "color": TEXT_MUTED, "letterSpacing": "0.1em", "marginLeft": "8px"}),
        ]),
        html.Div([
            html.Span("● ", style={"color": ACCENT_GREEN, "fontSize": "10px"}),
            html.Span(id="header-time", style={"fontFamily": FONT_MONO, "fontSize": "11px", "color": TEXT_MUTED}),
            html.Span(" | ", style={"color": TEXT_DIM}),
            dcc.Dropdown(
                id="time-range",
                options=[{"label": "24h", "value": 24}, {"label": "7d", "value": 168}, {"label": "30d", "value": 720}],
                value=24, clearable=False, searchable=False,
                style={"width": "80px", "display": "inline-block", "marginLeft": "8px", "color": "#000"}
            ),
            html.Span(id="isp-display", style={"fontFamily": FONT_MONO, "fontSize": "10px", "color": TEXT_DIM, "marginLeft": "16px"}),
            html.Span(id="alert-badges", style={"marginLeft": "12px"}),
        ], style={"display": "flex", "alignItems": "center"}),
    ], style={
        "display": "flex", "justifyContent": "space-between", "alignItems": "center",
        "padding": "16px 24px", "borderBottom": f"1px solid {BORDER}",
        "backgroundColor": BG_PANEL, "position": "sticky", "top": "0", "zIndex": "100",
    }),

    # Tabs
    html.Div([
        html.Div("Overview", id="tab-overview", className="tab tab--selected", n_clicks=0),
        html.Div("Latency & Routing", id="tab-latency", className="tab", n_clicks=0),
        html.Div("ISP & Health", id="tab-isp", className="tab", n_clicks=0),
    ], className="tab-container", style={"padding": "0 24px"}),

    # Content area
    html.Div(id="dashboard-content", style={"padding": "20px 24px", "maxWidth": "1600px", "margin": "0 auto"}),
], style={"backgroundColor": BG_PAGE, "minHeight": "100vh"})

# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

@app.callback(
    Output("header-time", "children"),
    Output("cached-data", "data"),
    Input("tick", "n_intervals")
)
def update_clock_and_cache(n):
    now = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
    dfs = {}
    for name in ["ookla", "fast", "iperf3", "ndt7", "curl", "ping", "dns", "mtr"]:
        df = load_csv(f"{name}.csv")
        if df is not None and not df.empty:
            df_copy = df.copy()
            df_copy["timestamp"] = df_copy["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%S")
            dfs[name] = df_copy.to_dict("records")
    return now, dfs

@app.callback(
    Output("isp-display", "children"),
    Output("alert-badges", "children"),
    Input("cached-data", "data")
)
def update_header_info(data):
    if not data:
        return "ISP: —", []
    dfs = {name: pd.DataFrame(records) for name, records in data.items()}
    for df in dfs.values():
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
    # ISP info
    isp_text = "ISP: —"
    if "ookla" in dfs and not dfs["ookla"].empty and "isp" in dfs["ookla"].columns:
        latest = dfs["ookla"].iloc[-1]
        isp_text = f"ISP: {latest['isp']}"
    # Alert badges
    badges = []
    ookla = dfs.get("ookla")
    if ookla is not None:
        dl = latest_val(ookla, "download_mbps")
        avg_dl = avg_val(ookla, "download_mbps", 24)
        if dl and avg_dl and dl < avg_dl * 0.8:
            badges.append(html.Span("DL LOW", className="alert-badge"))
        sr = success_rate(ookla, 24)
        if sr is not None and sr < 90:
            badges.append(html.Span("SUCCESS ↓", className="alert-badge warning"))
    fast = dfs.get("fast")
    if fast is not None:
        bloat = latest_val(fast, "bufferbloat_ms")
        if bloat and bloat > 100:
            badges.append(html.Span("BLOAT", className="alert-badge"))
    ping = dfs.get("ping")
    if ping is not None and "host_label" in ping.columns:
        cf = ping[ping["host_label"] == "Cloudflare-DNS-JHB"]
        if not cf.empty:
            loss = latest_val(cf, "packet_loss_pct")
            if loss and loss > 1.0:
                badges.append(html.Span("LOSS", className="alert-badge warning"))
    return isp_text, badges

@app.callback(
    Output("dashboard-content", "children"),
    Output("tab-overview", "className"),
    Output("tab-latency", "className"),
    Output("tab-isp", "className"),
    Input("tab-overview", "n_clicks"),
    Input("tab-latency", "n_clicks"),
    Input("tab-isp", "n_clicks"),
    Input("cached-data", "data"),
    Input("time-range", "value")
)
def render_content(n1, n2, n3, data, hours):
    # Determine active tab
    ctx = dash.callback_context
    if not ctx.triggered:
        active_tab = "overview"
    else:
        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
        if trigger_id == "tab-overview": active_tab = "overview"
        elif trigger_id == "tab-latency": active_tab = "latency"
        elif trigger_id == "tab-isp": active_tab = "isp"
        else: active_tab = "overview"

    tab_classes = {
        "overview": "tab tab--selected" if active_tab == "overview" else "tab",
        "latency": "tab tab--selected" if active_tab == "latency" else "tab",
        "isp": "tab tab--selected" if active_tab == "isp" else "tab",
    }

    if not data:
        return html.Div("No data.", style={"color": TEXT_MUTED}), tab_classes["overview"], tab_classes["latency"], tab_classes["isp"]

    dfs_full = {name: pd.DataFrame(records) for name, records in data.items()}
    for df in dfs_full.values():
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])

    # Filter by time range
    dfs = {name: get_filtered_data(df, hours) for name, df in dfs_full.items()}

    if active_tab == "overview":
        content = render_overview_tab(dfs, hours)
    elif active_tab == "latency":
        content = render_latency_tab(dfs)
    else:
        content = render_isp_tab(dfs_full, dfs, hours)

    return content, tab_classes["overview"], tab_classes["latency"], tab_classes["isp"]

# ---------------------------------------------------------------------------
# Tab rendering functions (complete with all original panels)
# ---------------------------------------------------------------------------

def render_overview_tab(dfs, hours):
    df_ookla = dfs.get("ookla")
    df_fast  = dfs.get("fast")
    df_iperf = dfs.get("iperf3")
    df_ndt7  = dfs.get("ndt7")
    df_curl  = dfs.get("curl")

    # KPI strip
    ookla_dl  = latest_val(df_ookla, "download_mbps")
    ookla_ul  = latest_val(df_ookla, "upload_mbps")
    ookla_png = latest_val(df_ookla, "ping_ms")
    avg_dl    = avg_val(df_ookla, "download_mbps", 24)
    avg_ul    = avg_val(df_ookla, "upload_mbps",   24)
    sr_ookla  = success_rate(df_ookla, 24)
    bloat     = latest_val(df_fast, "bufferbloat_ms")

    kpi_strip = html.Div([
        stat_card("DOWNLOAD",      fmt(ookla_dl),  "Mbps", ACCENT_GREEN, sub=f"24h avg: {fmt(avg_dl)} Mbps"),
        stat_card("UPLOAD",        fmt(ookla_ul),  "Mbps", ACCENT_BLUE, sub=f"24h avg: {fmt(avg_ul)} Mbps"),
        stat_card("PING",          fmt(ookla_png), "ms",   ACCENT_AMBER),
        stat_card("BUFFERBLOAT",   fmt(bloat),     "ms",   ACCENT_GREEN if (bloat or 999) < 50 else (ACCENT_AMBER if (bloat or 999) < 100 else ACCENT_RED)),
        stat_card("NDT7 DL",       fmt(latest_val(df_ndt7, "download_mbps")), "Mbps", ACCENT_PURPLE),
        stat_card("SUCCESS",       fmt(sr_ookla,0),"%",    ACCENT_GREEN if (sr_ookla or 0)>=90 else ACCENT_RED),
    ], style={"display": "flex", "gap": "2px", "marginBottom": "20px", "flexWrap": "wrap"})

    # Ookla
    fig_ookla = make_fig()
    make_line(fig_ookla, df_ookla, "download_mbps", "Download", ACCENT_GREEN)
    make_line(fig_ookla, df_ookla, "upload_mbps",   "Upload",   ACCENT_BLUE)
    add_anomaly_band(fig_ookla, df_ookla, "download_mbps", ACCENT_GREEN)
    fig_ookla.update_layout(yaxis_title="Mbps", height=200)

    fig_ping_ookla = make_fig()
    make_line(fig_ping_ookla, df_ookla, "ping_ms", "Ping", ACCENT_AMBER)
    add_anomaly_band(fig_ping_ookla, df_ookla, "ping_ms", ACCENT_AMBER)
    fig_ping_ookla.update_layout(yaxis_title="ms", height=200)

    ookla_panel = chart_panel([
        section_header("OOKLA SPEEDTEST", "every 20 min"),
        html.Div([
            html.Div([dcc.Graph(figure=fig_ookla, config={"displayModeBar": False}, style={"height": "200px"})], style={"flex": "2"}),
            html.Div([dcc.Graph(figure=fig_ping_ookla, config={"displayModeBar": False}, style={"height": "200px"})], style={"flex": "1"}),
        ], style={"display": "flex", "gap": "2px"}),
    ])

    # fast + ndt7
    fig_fast = make_fig()
    make_line(fig_fast, df_fast, "download_mbps",  "Download",   ACCENT_GREEN)
    make_line(fig_fast, df_fast, "upload_mbps",    "Upload",     ACCENT_BLUE)
    make_line(fig_fast, df_fast, "latency_ms",     "Latency",    ACCENT_AMBER, dash="dot")
    make_line(fig_fast, df_fast, "bufferbloat_ms", "Bufferbloat",ACCENT_RED,   dash="dash")
    fig_fast.update_layout(yaxis_title="Mbps / ms", height=200)

    fig_ndt7 = make_fig()
    make_line(fig_ndt7, df_ndt7, "download_mbps", "Download", ACCENT_GREEN)
    make_line(fig_ndt7, df_ndt7, "upload_mbps",   "Upload",   ACCENT_BLUE)
    make_line(fig_ndt7, df_ndt7, "rtt_ms",        "RTT",      ACCENT_AMBER, dash="dot")
    fig_ndt7.update_layout(yaxis_title="Mbps / ms", height=200)

    row_fast_ndt7 = html.Div([
        html.Div([chart_panel([section_header("FAST.COM"), dcc.Graph(figure=fig_fast, config={"displayModeBar": False}, style={"height": "200px"})])], style={"flex": "1"}),
        html.Div([chart_panel([section_header("NDT7"), dcc.Graph(figure=fig_ndt7, config={"displayModeBar": False}, style={"height": "200px"})])], style={"flex": "1"}),
    ], style={"display": "flex", "gap": "2px", "marginTop": "2px"})

    # iperf3
    fig_iperf = make_fig()
    make_line(fig_iperf, df_iperf, "download_mbps", "Download", ACCENT_GREEN)
    make_line(fig_iperf, df_iperf, "upload_mbps",   "Upload",   ACCENT_BLUE)
    fig_iperf.update_layout(yaxis_title="Mbps", height=180)
    iperf_server = latest_val(df_iperf, "server") if df_iperf is not None else None
    iperf_tag = f"last server: {iperf_server}" if iperf_server else "every 20 min"
    iperf_panel = chart_panel([section_header("IPERF3", iperf_tag), dcc.Graph(figure=fig_iperf, config={"displayModeBar": False}, style={"height": "180px"})])

    # cURL (light/heavy/superheavy) – fully implemented as in original
    curl_targets = {}
    if df_curl is not None and "target_name" in df_curl.columns:
        for tname, tdf in df_curl.groupby("target_name"):
            curl_targets[tname] = tdf.reset_index(drop=True)

    curl_superheavy = {}
    if df_curl is not None and "file_size_mb" in df_curl.columns:
        sh = df_curl[df_curl["file_size_mb"] >= 9000]
        for tname, tdf in sh.groupby("target_name"):
            curl_superheavy[tname] = tdf.reset_index(drop=True)

    CURL_COLORS = {"hetzner_fsn1": ACCENT_GREEN, "hetzner_ash": ACCENT_BLUE, "hetzner_hel1": ACCENT_AMBER, "ubuntu_noble": ACCENT_PURPLE}
    CURL_LABELS = {
        "hetzner_fsn1": "Hetzner FSN1 (Frankfurt)",
        "hetzner_ash":  "Hetzner ASH (Ashburn)",
        "hetzner_hel1": "Hetzner HEL1 (Helsinki)",
        "ubuntu_noble": "Ubuntu ISO / Canonical CDN",
    }

    def curl_filter(k, min_mb, max_mb):
        if k not in curl_targets:
            return None
        tdf = curl_targets[k]
        if "file_size_mb" not in tdf.columns:
            return tdf
        return tdf[(tdf["file_size_mb"] >= min_mb) & (tdf["file_size_mb"] <= max_mb)]

    fig_curl_light = make_fig()
    for k in ["hetzner_fsn1", "hetzner_ash", "hetzner_hel1"]:
        tdf = curl_filter(k, 50, 200)
        if tdf is not None and not tdf.empty:
            make_line(fig_curl_light, tdf, "download_mbps", CURL_LABELS.get(k,k), CURL_COLORS.get(k, TEXT_MUTED))
    fig_curl_light.update_layout(yaxis_title="Mbps", height=200)

    fig_curl_heavy = make_fig()
    for k in ["hetzner_fsn1", "hetzner_ash", "ubuntu_noble"]:
        tdf = curl_filter(k, 201, 9000)
        if tdf is not None and not tdf.empty:
            make_line(fig_curl_heavy, tdf, "download_mbps", CURL_LABELS.get(k,k), CURL_COLORS.get(k, TEXT_MUTED))
    fig_curl_heavy.update_layout(yaxis_title="Mbps", height=200)

    curl_stats = []
    stat_configs = [
        ("hetzner_fsn1",  50,  200), ("hetzner_ash",   50,  200), ("hetzner_hel1",  50,  200),
        ("hetzner_fsn1", 201, 2000), ("hetzner_ash",  201, 2000), ("ubuntu_noble",  50, 9000),
    ]
    stat_labels = {
        ("hetzner_fsn1",  50,  200): "FSN1 100MB", ("hetzner_ash",   50,  200): "ASH 100MB", ("hetzner_hel1",  50,  200): "HEL1 100MB",
        ("hetzner_fsn1", 201, 2000): "FSN1 1GB", ("hetzner_ash",  201, 2000): "ASH 1GB", ("ubuntu_noble",  50, 9000): "Ubuntu ISO",
    }
    for (k, mn, mx) in stat_configs:
        tdf = curl_filter(k, mn, mx)
        if tdf is not None and not tdf.empty:
            lv = tdf["download_mbps"].dropna().iloc[-1] if not tdf["download_mbps"].dropna().empty else None
            av = tdf["download_mbps"].dropna().mean() if not tdf["download_mbps"].dropna().empty else None
            curl_stats.append(stat_card(stat_labels[(k,mn,mx)].upper(), fmt(lv), "Mbps", CURL_COLORS.get(k,TEXT_MUTED), sub=f"avg: {fmt(av)} Mbps"))

    curl_panel = chart_panel([
        section_header("CURL DOWNLOAD TARGETS", "real files / no disk write"),
        html.Div(curl_stats, style={"display": "flex", "gap": "2px", "marginBottom": "12px", "flexWrap": "wrap"}),
        html.Div([
            html.Div([html.Div("100 MB — 3× routing paths", style={"fontFamily": FONT_MONO, "fontSize": "10px", "color": TEXT_DIM}),
                      dcc.Graph(figure=fig_curl_light, config={"displayModeBar": False}, style={"height": "200px"})], style={"flex": "2"}),
            html.Div([html.Div("LARGE FILE — sustained throughput", style={"fontFamily": FONT_MONO, "fontSize": "10px", "color": TEXT_DIM}),
                      dcc.Graph(figure=fig_curl_heavy, config={"displayModeBar": False}, style={"height": "200px"})], style={"flex": "1"}),
        ], style={"display": "flex", "gap": "16px"}),
    ])

    fig_sh = make_fig()
    sh_cards = []
    for k, color in [("hetzner_fsn1", ACCENT_GREEN), ("hetzner_ash", ACCENT_BLUE)]:
        if k in curl_superheavy:
            tdf = curl_superheavy[k]
            make_line(fig_sh, tdf, "download_mbps", CURL_LABELS.get(k,k), color, mode="lines+markers")
            lv = tdf["download_mbps"].dropna().iloc[-1] if not tdf["download_mbps"].dropna().empty else None
            av = tdf["download_mbps"].dropna().mean() if not tdf["download_mbps"].dropna().empty else None
            sh_cards.append(stat_card(f"10GB {CURL_LABELS.get(k,k)}", fmt(lv), "Mbps", color, sub=f"all-time avg: {fmt(av)} Mbps"))
    fig_sh.update_layout(yaxis_title="Mbps", height=200)
    sh_panel = chart_panel([
        section_header("10 GB SUSTAINED DOWNLOAD", "once per day — best-case line speed"),
        html.Div(sh_cards, style={"display": "flex", "gap": "2px", "marginBottom": "12px", "flexWrap": "wrap"}),
        dcc.Graph(figure=fig_sh, config={"displayModeBar": False}, style={"height": "200px"}),
    ])

    # 24h averages table (original)
    rows = []
    sources = [("Ookla", df_ookla, "download_mbps", "upload_mbps"),
               ("Fast.com", df_fast, "download_mbps", "upload_mbps"),
               ("NDT7", df_ndt7, "download_mbps", "upload_mbps"),
               ("iPerf3", df_iperf, "download_mbps", "upload_mbps")]
    cell = lambda txt, color=TEXT_PRIMARY: html.Td(txt, style={"fontFamily": FONT_MONO, "fontSize": "12px", "color": color, "padding": "8px 16px", "borderBottom": f"1px solid {BG_PANEL2}"})
    for sname, df, dcol, ucol in sources:
        a_dl = avg_val(df, dcol, 24)
        a_ul = avg_val(df, ucol, 24)
        p_dl = avg_val(df, dcol, 1)
        sr = success_rate(df, 24)
        sr_color = ACCENT_GREEN if (sr or 0) >= 95 else (ACCENT_AMBER if (sr or 0) >= 80 else ACCENT_RED)
        rows.append(html.Tr([cell(sname, TEXT_MUTED), cell(fmt(a_dl), ACCENT_GREEN), cell(fmt(a_ul), ACCENT_BLUE), cell(fmt(p_dl), ACCENT_AMBER), cell(fmt(sr,0)+"%", sr_color)]))
    summary_panel = chart_panel([
        section_header("24-HOUR AVERAGES", "all sources"),
        html.Table([html.Thead(html.Tr([html.Th(h, style={"fontFamily": FONT_MONO, "fontSize": "10px", "color": TEXT_DIM, "padding": "6px 16px", "textAlign": "left", "borderBottom": f"1px solid {BORDER}"}) for h in ["SOURCE", "AVG DL (Mbps)", "AVG UL (Mbps)", "LAST 1H DL (Mbps)", "SUCCESS RATE 24H"]])),
                    html.Tbody(rows)], style={"width": "100%", "borderCollapse": "collapse"}),
    ])

    footer = html.Div([
        html.Span("SIGMON", style={"color": ACCENT_AMBER, "fontFamily": FONT_MONO, "fontSize": "10px", "letterSpacing": "0.15em"}),
        html.Span(f"  //  LOG DIR: {LOG_DIR}  //  PORT 8050", style={"fontFamily": FONT_MONO, "fontSize": "10px", "color": TEXT_DIM}),
    ], style={"borderTop": f"1px solid {BORDER}", "padding": "12px 0", "marginTop": "20px"})

    return html.Div([
        kpi_strip,
        ookla_panel, GAP,
        row_fast_ndt7, GAP,
        iperf_panel, GAP,
        curl_panel, GAP,
        sh_panel, GAP,
        summary_panel,
        footer,
    ], className="panel")

def render_latency_tab(dfs):
    df_ping = dfs.get("ping")
    df_dns  = dfs.get("dns")
    df_mtr  = dfs.get("mtr")

    # Group ping by host_label
    ping_by_host = {}
    if df_ping is not None and "host_label" in df_ping.columns:
        for label, tdf in df_ping.groupby("host_label"):
            ping_by_host[label] = tdf.reset_index(drop=True)

    # Group dns by resolver
    dns_by_resolver = {}
    if df_dns is not None and "resolver" in df_dns.columns:
        for label, tdf in df_dns.groupby("resolver"):
            dns_by_resolver[label] = tdf.reset_index(drop=True)

    # Group mtr by label
    mtr_by_label = {}
    if df_mtr is not None and "label" in df_mtr.columns:
        for label, tdf in df_mtr.groupby("label"):
            mtr_by_label[label] = tdf.reset_index(drop=True)

    PING_COLORS = {"Cloudflare-DNS-JHB": ACCENT_GREEN, "Google-DNS": ACCENT_BLUE, "MLab-JHB": ACCENT_AMBER, "JHB-Local": ACCENT_PURPLE}
    fig_latency = make_fig()
    fig_loss    = make_fig()
    fig_jitter  = make_fig()
    for label, color in PING_COLORS.items():
        df_h = ping_by_host.get(label)
        if df_h is not None:
            make_line(fig_latency, df_h, "avg_ms", label, color)
            make_line(fig_loss,    df_h, "packet_loss_pct", label, color)
            make_line(fig_jitter,  df_h, "jitter_ms", label, color)
    fig_latency.update_layout(yaxis_title="ms", height=180)
    fig_loss.update_layout(yaxis_title="% loss", height=180)
    fig_jitter.update_layout(yaxis_title="ms", height=180)

    ping_cards = []
    for label, color in PING_COLORS.items():
        df_h = ping_by_host.get(label)
        lv = latest_val(df_h, "avg_ms")
        loss = latest_val(df_h, "packet_loss_pct")
        ping_cards.append(mini_stat(label.replace("-"," "), fmt(lv), "ms", ACCENT_GREEN if (lv or 999)<20 else (ACCENT_AMBER if (lv or 999)<60 else ACCENT_RED)))
        ping_cards.append(mini_stat(f"{label[:8]} LOSS", fmt(loss,1), "%", ACCENT_GREEN if (loss or 1)<0.5 else (ACCENT_AMBER if (loss or 1)<2 else ACCENT_RED)))

    ping_panel = chart_panel([
        section_header("PING / PACKET LOSS / JITTER", "every 20 min"),
        html.Div(ping_cards, style={"display": "flex", "gap": "2px", "marginBottom": "12px", "flexWrap": "wrap"}),
        html.Div([
            html.Div([html.Div("LATENCY (avg ms)", style={"fontFamily": FONT_MONO, "fontSize": "10px", "color": TEXT_DIM}), dcc.Graph(figure=fig_latency, config={"displayModeBar": False}, style={"height": "180px"})], style={"flex": "2"}),
            html.Div([html.Div("PACKET LOSS (%)", style={"fontFamily": FONT_MONO, "fontSize": "10px", "color": TEXT_DIM}), dcc.Graph(figure=fig_loss, config={"displayModeBar": False}, style={"height": "180px"})], style={"flex": "1"}),
            html.Div([html.Div("JITTER (mdev ms)", style={"fontFamily": FONT_MONO, "fontSize": "10px", "color": TEXT_DIM}), dcc.Graph(figure=fig_jitter, config={"displayModeBar": False}, style={"height": "180px"})], style={"flex": "1"}),
        ], style={"display": "flex", "gap": "2px"}),
    ])

    DNS_COLORS = {"Cloudflare": ACCENT_GREEN, "Google": ACCENT_BLUE, "Quad9": ACCENT_AMBER}
    fig_dns = make_fig()
    for label, color in DNS_COLORS.items():
        df_r = dns_by_resolver.get(label)
        make_line(fig_dns, df_r, "lookup_ms", label, color)
    fig_dns.update_layout(yaxis_title="ms", height=160)
    dns_cards = []
    for label, color in DNS_COLORS.items():
        df_r = dns_by_resolver.get(label)
        lv = latest_val(df_r, "lookup_ms")
        dns_cards.append(mini_stat(label, fmt(lv), "ms", ACCENT_GREEN if (lv or 999)<50 else (ACCENT_AMBER if (lv or 999)<150 else ACCENT_RED)))
    dns_panel = chart_panel([
        section_header("DNS RESOLVER LATENCY", "every 20 min"),
        html.Div(dns_cards, style={"display": "flex", "gap": "2px", "marginBottom": "12px"}),
        dcc.Graph(figure=fig_dns, config={"displayModeBar": False}, style={"height": "160px"}),
    ])

    MTR_COLORS = {"NAPAfrica-JHB": ACCENT_GREEN, "TENET-JHB": ACCENT_BLUE, "Dota2-CS2-JHB": ACCENT_AMBER, "Valorant-JHB": ACCENT_PURPLE,
                  "AWS-CapeTown": ACCENT_RED, "Netflix-OC-JHB": ACCENT_GREEN, "Seacom-London": ACCENT_BLUE, "AMS-IX-Europe": ACCENT_AMBER,
                  "Cloudflare-DNS": ACCENT_PURPLE, "Google-DNS": ACCENT_RED}
    fig_mtr_lat = make_fig()
    fig_mtr_loss = make_fig()
    mtr_cards = []
    for label, color in MTR_COLORS.items():
        df_m = mtr_by_label.get(label)
        if df_m is not None:
            make_line(fig_mtr_lat, df_m, "avg_ms", label, color)
            make_line(fig_mtr_loss, df_m, "loss_pct", label, color)
            lv_avg = latest_val(df_m, "avg_ms")
            lv_loss = latest_val(df_m, "loss_pct")
            mtr_cards.append(mini_stat(label.replace("-"," ").upper(), fmt(lv_avg), "ms", ACCENT_GREEN if (lv_avg or 999)<30 else (ACCENT_AMBER if (lv_avg or 999)<80 else ACCENT_RED)))
            mtr_cards.append(mini_stat(f"{label[:10]} LOSS", fmt(lv_loss,1), "%", ACCENT_GREEN if (lv_loss or 1)<0.5 else (ACCENT_AMBER if (lv_loss or 1)<2 else ACCENT_RED)))
    fig_mtr_lat.update_layout(yaxis_title="ms", height=200)
    fig_mtr_loss.update_layout(yaxis_title="% loss", height=200)
    mtr_panel = chart_panel([
        section_header("MTR (PingPlotter) – PATH LATENCY & LOSS", "every 20 min"),
        html.Div(mtr_cards, style={"display": "flex", "gap": "2px", "marginBottom": "12px", "flexWrap": "wrap"}),
        html.Div([
            html.Div([html.Div("AVG LATENCY (ms)", style={"fontFamily": FONT_MONO, "fontSize": "10px", "color": TEXT_DIM}), dcc.Graph(figure=fig_mtr_lat, config={"displayModeBar": False}, style={"height": "200px"})], style={"flex": "2"}),
            html.Div([html.Div("PACKET LOSS (%)", style={"fontFamily": FONT_MONO, "fontSize": "10px", "color": TEXT_DIM}), dcc.Graph(figure=fig_mtr_loss, config={"displayModeBar": False}, style={"height": "200px"})], style={"flex": "1"}),
        ], style={"display": "flex", "gap": "2px"}),
    ])

    return html.Div([ping_panel, GAP, dns_panel, GAP, mtr_panel], className="panel")

def render_isp_tab(full_dfs, filtered_dfs, hours):
    # Health score gauge
    ookla = full_dfs.get("ookla")
    fast  = full_dfs.get("fast")
    ping  = full_dfs.get("ping")
    score = 100
    if ookla is not None:
        dl = latest_val(ookla, "download_mbps")
        avg_dl = avg_val(ookla, "download_mbps", 24)
        if dl and avg_dl:
            ratio = dl / avg_dl
            if ratio < 0.5: score -= 20
            elif ratio < 0.8: score -= 10
        sr = success_rate(ookla, 24)
        if sr is not None:
            if sr < 80: score -= 20
            elif sr < 95: score -= 10
    if fast is not None:
        bloat = latest_val(fast, "bufferbloat_ms")
        if bloat:
            if bloat > 200: score -= 15
            elif bloat > 100: score -= 8
    if ping is not None and "host_label" in ping.columns:
        cf = ping[ping["host_label"] == "Cloudflare-DNS-JHB"]
        if not cf.empty:
            loss = latest_val(cf, "packet_loss_pct")
            if loss:
                if loss > 5: score -= 20
                elif loss > 1: score -= 10
    score = max(0, min(100, score))
    color = ACCENT_GREEN if score >= 80 else (ACCENT_AMBER if score >= 50 else ACCENT_RED)
    gauge_fig = go.Figure(go.Indicator(mode="gauge+number", value=score, number={"font":{"color":color,"size":40,"family":FONT_MONO}},
                                       gauge={"axis":{"range":[0,100],"tickcolor":TEXT_MUTED},"bar":{"color":color},"bgcolor":"rgba(0,0,0,0)",
                                              "steps":[{"range":[0,50],"color":f"rgba({_hex_to_rgba(ACCENT_RED,0.2)})"},
                                                       {"range":[50,80],"color":f"rgba({_hex_to_rgba(ACCENT_AMBER,0.2)})"},
                                                       {"range":[80,100],"color":f"rgba({_hex_to_rgba(ACCENT_GREEN,0.2)})"}]}))
    gauge_fig.update_layout(height=150, margin=dict(l=20,r=20,t=30,b=10))

    # ISP details
    isp_name = "Unknown"
    if ookla is not None and not ookla.empty and "isp" in ookla.columns:
        isp_name = ookla.iloc[-1]["isp"]
    isp_card = stat_card("ISP", isp_name, "", ACCENT_BLUE)

    # Compare mode (simplified date pickers)
    compare_card = chart_panel([
        section_header("Compare Ookla Download"),
        dbc.Row([
            dbc.Col(dcc.DatePickerSingle(id="date1", date=datetime.now().date()-timedelta(days=1), display_format="YYYY-MM-DD")),
            dbc.Col(dcc.DatePickerSingle(id="date2", date=datetime.now().date(), display_format="YYYY-MM-DD")),
        ]) if 'dbc' in globals() else html.Div("Install dash-bootstrap-components for date pickers"),
        dcc.Graph(id="compare-graph", config={"displayModeBar": False}, style={"height": "250px"})
    ])

    return html.Div([
        dbc.Row([dbc.Col(isp_card, width=4), dbc.Col(dcc.Graph(figure=gauge_fig, config={"displayModeBar": False}), width=8)]) if 'dbc' in globals() else html.Div([isp_card, dcc.Graph(figure=gauge_fig)]),
        GAP,
        compare_card,
    ], className="panel")

# Compare graph callback
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=False)