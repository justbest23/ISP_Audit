#!/usr/bin/env python3
"""
SIGMON // Network Speed Monitor
Dark terminal aesthetic with tabs, alerts, health score,
anomaly bands, compare mode, ISP info, Eweka, ping/DNS/MTR panels.
"""
import dash
from dash import dcc, html, Input, Output, State
import pandas as pd
import plotly.graph_objects as go
import os
from datetime import datetime, timedelta
import dash_bootstrap_components as dbc

LOG_DIR = "/home/troggoman/speedtests/logs"

# ---------------------------------------------------------------------------
# Design tokens — user's customised values, do not change
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
ACCENT_PINK  = "#ff6b9d"
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
    if d.empty:
        return
    fig.add_trace(go.Scatter(
        x=d["timestamp"], y=d[col], name=name, mode=mode,
        line=dict(color=color, width=1.5, dash=dash),
        hovertemplate=f"%{{y:.1f}}<extra>{name}</extra>",
    ))

def _hex_to_rgba(hex_color, alpha):
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"{r},{g},{b},{alpha}"

def add_anomaly_band(fig, df, col, color):
    """Rolling 24h median ± 2σ band."""
    if df is None or col not in df.columns or df.empty or len(df) < 20:
        return
    d = df[["timestamp", col]].dropna().sort_values("timestamp").set_index("timestamp")
    hourly = d.resample("1h").median()
    rm = hourly[col].rolling(window=24, min_periods=6).median()
    rs = hourly[col].rolling(window=24, min_periods=6).std()
    upper = (rm + 2 * rs).dropna()
    lower = (rm - 2 * rs).dropna()
    idx = upper.index
    if idx.empty:
        return
    fig.add_trace(go.Scatter(x=idx, y=upper, mode="lines", line=dict(width=0),
                             showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=idx, y=lower, mode="lines",
                             fill="tonexty",
                             fillcolor=f"rgba({_hex_to_rgba(color, 0.12)})",
                             line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=idx, y=rm.loc[idx], mode="lines",
                             name=f"{col} 24h median",
                             line=dict(color=color, width=1, dash="dot"),
                             hoverinfo="skip"))

# ---------------------------------------------------------------------------
# UI components
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
# Curl helpers (shared across tabs)
# ---------------------------------------------------------------------------

CURL_COLORS = {
    "hetzner_fsn1": ACCENT_GREEN,
    "hetzner_ash":  ACCENT_BLUE,
    "hetzner_hel1": ACCENT_AMBER,
    "ubuntu_noble": ACCENT_PURPLE,
    "eweka":        ACCENT_PINK,
}
CURL_LABELS = {
    "hetzner_fsn1": "Hetzner FSN1 (Frankfurt)",
    "hetzner_ash":  "Hetzner ASH (Ashburn)",
    "hetzner_hel1": "Hetzner HEL1 (Helsinki)",
    "ubuntu_noble": "Ubuntu ISO / Canonical CDN",
    "eweka":        "Eweka Usenet (Amsterdam)",
}

def curl_filter(curl_targets, k, min_mb, max_mb):
    if k not in curl_targets:
        return None
    tdf = curl_targets[k]
    if "file_size_mb" not in tdf.columns:
        return tdf
    return tdf[(tdf["file_size_mb"] >= min_mb) & (tdf["file_size_mb"] <= max_mb)]

def build_curl_targets(df_curl):
    targets = {}
    if df_curl is not None and "target_name" in df_curl.columns:
        for tname, tdf in df_curl.groupby("target_name"):
            targets[tname] = tdf.reset_index(drop=True)
    return targets

def build_curl_superheavy(df_curl):
    sh = {}
    if df_curl is not None and "file_size_mb" in df_curl.columns:
        for tname, tdf in df_curl[df_curl["file_size_mb"] >= 9000].groupby("target_name"):
            sh[tname] = tdf.reset_index(drop=True)
    return sh

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = dash.Dash(__name__, title="SIGMON // Speed Monitor",
                suppress_callback_exceptions=True)
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

        /* Tabs */
        .tab-container { display: flex; border-bottom: 1px solid #1e2a35; margin-bottom: 16px; }
        .tab {
            font-family: 'JetBrains Mono', monospace; font-size: 11px; font-weight: 600;
            letter-spacing: 0.15em; text-transform: uppercase; color: #b6bfc5;
            padding: 10px 20px; cursor: pointer; border-bottom: 2px solid transparent;
            transition: color 0.1s, border-color 0.1s; user-select: none;
        }
        .tab:hover { color: #e8edf2; }
        .tab--selected { color: #f0a500; border-bottom-color: #f0a500; }

        /* Alert badges */
        .alert-badge {
            display: inline-block; font-family: 'JetBrains Mono'; font-size: 9px;
            background: #f05454; color: #fff; padding: 2px 6px; border-radius: 10px;
            margin-left: 6px; text-transform: uppercase; letter-spacing: 0.05em;
        }
        .alert-badge.warning { background: #f0a500; color: #000; }

        /* Date pickers — force dark theme */
        .DateInput_input {
            background: #0f1318 !important; color: #e8edf2 !important;
            border-color: #1e2a35 !important; font-family: 'JetBrains Mono', monospace !important;
            font-size: 11px !important;
        }
        .DateRangePickerInput, .SingleDatePickerInput {
            background: #0f1318 !important; border-color: #1e2a35 !important;
        }
        .DayPicker { background: #0f1318 !important; }
        .DayPicker_weekHeader { color: #b6bfc5 !important; }
        .CalendarDay__default { background: #0f1318 !important; color: #b6bfc5 !important; border-color: #1e2a35 !important; }
        .CalendarDay__default:hover { background: #131920 !important; color: #e8edf2 !important; }
        .CalendarDay__selected { background: #f0a500 !important; color: #000 !important; border-color: #f0a500 !important; }
        .CalendarDay__selected:hover { background: #f0a500 !important; }
        .DayPickerNavigation_button { background: #0f1318 !important; border-color: #1e2a35 !important; }
        .DayPickerNavigation_button:hover { background: #131920 !important; }
        .CalendarMonthGrid { background: #0f1318 !important; }
        .CalendarMonth { background: #0f1318 !important; }
        .CalendarMonth_caption { color: #e8edf2 !important; }
        .DateInput_fang { display: none; }

        /* Dropdown override */
        .Select-control { background: #0f1318 !important; border-color: #1e2a35 !important; }
        .Select-value-label { color: #e8edf2 !important; }
        .Select-menu-outer { background: #0f1318 !important; border-color: #1e2a35 !important; }
        .Select-option { background: #0f1318 !important; color: #b6bfc5 !important; }
        .Select-option:hover, .Select-option.is-focused { background: #131920 !important; color: #e8edf2 !important; }
        .Select-option.is-selected { color: #f0a500 !important; }

        @media (max-width: 768px) { .flex-wrap-mobile { flex-wrap: wrap; } }
    </style>
</head>
<body>{%app_entry%}<footer>{%config%}{%scripts%}{%renderer%}</footer>
</body>
</html>
'''

app.layout = html.Div([
    dcc.Interval(id="tick", interval=120_000, n_intervals=0),
    dcc.Store(id="cached-data", storage_type="memory"),

    # ── Header ────────────────────────────────────────────────────────────────
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
            html.Span(" | ", style={"color": TEXT_DIM, "margin": "0 4px"}),
            dcc.Dropdown(
                id="time-range",
                options=[{"label": "24h", "value": 24},
                         {"label": "7d",  "value": 168},
                         {"label": "30d", "value": 720}],
                value=24, clearable=False, searchable=False,
                style={"width": "80px", "display": "inline-block",
                       "verticalAlign": "middle", "marginLeft": "4px"},
            ),
            html.Span(id="isp-display", style={"fontFamily": FONT_MONO, "fontSize": "10px",
                                                "color": TEXT_DIM, "marginLeft": "16px"}),
            html.Span(id="alert-badges", style={"marginLeft": "4px"}),
        ], style={"display": "flex", "alignItems": "center"}),
    ], style={
        "display": "flex", "justifyContent": "space-between", "alignItems": "center",
        "padding": "16px 24px", "borderBottom": f"1px solid {BORDER}",
        "backgroundColor": BG_PANEL, "position": "sticky", "top": "0", "zIndex": "100",
    }),

    # ── Tabs ──────────────────────────────────────────────────────────────────
    html.Div([
        html.Div("Overview",         id="tab-overview", className="tab tab--selected", n_clicks=0),
        html.Div("Latency & Routing",id="tab-latency",  className="tab", n_clicks=0),
        html.Div("ISP & Health",     id="tab-isp",      className="tab", n_clicks=0),
    ], className="tab-container", style={"padding": "0 24px", "marginTop": "4px"}),

    # ── Content ───────────────────────────────────────────────────────────────
    html.Div(id="dashboard-content",
             style={"padding": "20px 24px", "maxWidth": "1600px", "margin": "0 auto"}),

], style={"backgroundColor": BG_PAGE, "minHeight": "100vh"})

# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

@app.callback(
    Output("header-time",  "children"),
    Output("cached-data",  "data"),
    Input("tick", "n_intervals"),
)
def refresh_cache(n):
    now = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
    dfs = {}
    for name in ["ookla", "fast", "iperf3", "ndt7", "curl", "ping", "dns", "mtr"]:
        df = load_csv(f"{name}.csv")
        if df is not None and not df.empty:
            df2 = df.copy()
            df2["timestamp"] = df2["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%S")
            dfs[name] = df2.to_dict("records")
    return now, dfs


@app.callback(
    Output("isp-display",  "children"),
    Output("alert-badges", "children"),
    Input("cached-data", "data"),
)
def update_header_info(data):
    if not data:
        return "ISP: —", []
    dfs = _deserialise(data)

    isp_text = "ISP: —"
    ookla = dfs.get("ookla")
    if ookla is not None and not ookla.empty and "isp" in ookla.columns:
        isp_text = f"ISP: {ookla.iloc[-1]['isp']}"

    badges = []
    if ookla is not None:
        dl     = latest_val(ookla, "download_mbps")
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
    Output("tab-overview",      "className"),
    Output("tab-latency",       "className"),
    Output("tab-isp",           "className"),
    Input("tab-overview",  "n_clicks"),
    Input("tab-latency",   "n_clicks"),
    Input("tab-isp",       "n_clicks"),
    Input("cached-data",   "data"),
    Input("time-range",    "value"),
)
def render_content(n1, n2, n3, data, hours):
    ctx = dash.callback_context
    active = "overview"
    if ctx.triggered:
        tid = ctx.triggered[0]["prop_id"].split(".")[0]
        if tid == "tab-latency": active = "latency"
        elif tid == "tab-isp":   active = "isp"
        elif tid == "tab-overview": active = "overview"

    tc = {t: f"tab tab--selected" if t == active else "tab"
          for t in ("overview", "latency", "isp")}

    if not data:
        empty = html.Div("Waiting for data...",
                         style={"color": TEXT_MUTED, "fontFamily": FONT_MONO,
                                "padding": "40px", "textAlign": "center"})
        return empty, tc["overview"], tc["latency"], tc["isp"]

    dfs_full = _deserialise(data)
    dfs      = {k: get_filtered_data(v, hours) for k, v in dfs_full.items()}

    if active == "overview":
        content = _tab_overview(dfs)
    elif active == "latency":
        content = _tab_latency(dfs)
    else:
        content = _tab_isp(dfs_full, dfs)

    return content, tc["overview"], tc["latency"], tc["isp"]


@app.callback(
    Output("compare-graph", "figure"),
    Input("date1", "date"),
    Input("date2", "date"),
    Input("cached-data", "data"),
)
def update_compare(date1, date2, data):
    if not data or not date1 or not date2:
        return make_fig()
    ookla = _deserialise(data).get("ookla")
    if ookla is None:
        return make_fig()
    d1 = pd.to_datetime(date1).date()
    d2 = pd.to_datetime(date2).date()
    fig = make_fig()
    make_line(fig, ookla[ookla["timestamp"].dt.date == d1], "download_mbps", f"{d1} DL", ACCENT_GREEN)
    make_line(fig, ookla[ookla["timestamp"].dt.date == d2], "download_mbps", f"{d2} DL", ACCENT_BLUE)
    make_line(fig, ookla[ookla["timestamp"].dt.date == d1], "upload_mbps",   f"{d1} UL", ACCENT_GREEN, dash="dot")
    make_line(fig, ookla[ookla["timestamp"].dt.date == d2], "upload_mbps",   f"{d2} UL", ACCENT_BLUE,  dash="dot")
    fig.update_layout(yaxis_title="Mbps", height=250)
    return fig

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _deserialise(data):
    dfs = {}
    for name, records in data.items():
        df = pd.DataFrame(records)
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
        dfs[name] = df
    return dfs

# ---------------------------------------------------------------------------
# Tab: Overview
# ---------------------------------------------------------------------------

def _tab_overview(dfs):
    df_ookla = dfs.get("ookla")
    df_fast  = dfs.get("fast")
    df_iperf = dfs.get("iperf3")
    df_ndt7  = dfs.get("ndt7")
    df_curl  = dfs.get("curl")

    curl_targets  = build_curl_targets(df_curl)
    curl_superheavy = build_curl_superheavy(df_curl)

    # ── KPI strip ─────────────────────────────────────────────────────────────
    bloat    = latest_val(df_fast, "bufferbloat_ms")
    sr_ookla = success_rate(df_ookla, 24)
    kpi = html.Div([
        stat_card("DOWNLOAD",    fmt(latest_val(df_ookla, "download_mbps")), "Mbps", ACCENT_GREEN,
                  sub=f"24h avg: {fmt(avg_val(df_ookla,'download_mbps',24))} Mbps"),
        stat_card("UPLOAD",      fmt(latest_val(df_ookla, "upload_mbps")),   "Mbps", ACCENT_BLUE,
                  sub=f"24h avg: {fmt(avg_val(df_ookla,'upload_mbps',24))} Mbps"),
        stat_card("PING",        fmt(latest_val(df_ookla, "ping_ms")),       "ms",   ACCENT_AMBER),
        stat_card("BUFFERBLOAT", fmt(bloat), "ms",
                  ACCENT_GREEN if (bloat or 999) < 50 else (ACCENT_AMBER if (bloat or 999) < 100 else ACCENT_RED)),
        stat_card("NDT7 DL",     fmt(latest_val(df_ndt7, "download_mbps")),  "Mbps", ACCENT_PURPLE),
        stat_card("SUCCESS",     fmt(sr_ookla, 0), "%",
                  ACCENT_GREEN if (sr_ookla or 0) >= 90 else ACCENT_RED),
    ], style={"display": "flex", "gap": "2px", "marginBottom": "20px", "flexWrap": "wrap"})

    # ── Ookla ─────────────────────────────────────────────────────────────────
    fig_ookla = make_fig()
    make_line(fig_ookla, df_ookla, "download_mbps", "Download", ACCENT_GREEN)
    make_line(fig_ookla, df_ookla, "upload_mbps",   "Upload",   ACCENT_BLUE)
    add_anomaly_band(fig_ookla, df_ookla, "download_mbps", ACCENT_GREEN)
    fig_ookla.update_layout(yaxis_title="Mbps")

    fig_ping_ookla = make_fig()
    make_line(fig_ping_ookla, df_ookla, "ping_ms", "Ping", ACCENT_AMBER)
    add_anomaly_band(fig_ping_ookla, df_ookla, "ping_ms", ACCENT_AMBER)
    fig_ping_ookla.update_layout(yaxis_title="ms")

    ookla_panel = chart_panel([
        section_header("OOKLA SPEEDTEST", "every 20 min"),
        html.Div([
            html.Div([dcc.Graph(figure=fig_ookla,      config={"displayModeBar": False}, style={"height": "200px"})], style={"flex": "2"}),
            html.Div([dcc.Graph(figure=fig_ping_ookla, config={"displayModeBar": False}, style={"height": "200px"})], style={"flex": "1"}),
        ], style={"display": "flex", "gap": "2px"}),
    ])

    # ── fast + ndt7 ───────────────────────────────────────────────────────────
    fig_fast = make_fig()
    make_line(fig_fast, df_fast, "download_mbps",  "Download",    ACCENT_GREEN)
    make_line(fig_fast, df_fast, "upload_mbps",    "Upload",      ACCENT_BLUE)
    make_line(fig_fast, df_fast, "latency_ms",     "Latency",     ACCENT_AMBER, dash="dot")
    make_line(fig_fast, df_fast, "bufferbloat_ms", "Bufferbloat", ACCENT_RED,   dash="dash")
    fig_fast.update_layout(yaxis_title="Mbps / ms")

    fig_ndt7 = make_fig()
    make_line(fig_ndt7, df_ndt7, "download_mbps", "Download", ACCENT_GREEN)
    make_line(fig_ndt7, df_ndt7, "upload_mbps",   "Upload",   ACCENT_BLUE)
    make_line(fig_ndt7, df_ndt7, "rtt_ms",        "RTT",      ACCENT_AMBER, dash="dot")
    fig_ndt7.update_layout(yaxis_title="Mbps / ms")

    row_fn = html.Div([
        html.Div([chart_panel([section_header("FAST.COM", "every 20 min"),
                               dcc.Graph(figure=fig_fast, config={"displayModeBar": False}, style={"height": "200px"})])], style={"flex": "1"}),
        html.Div([chart_panel([section_header("NDT7",     "every 20 min"),
                               dcc.Graph(figure=fig_ndt7, config={"displayModeBar": False}, style={"height": "200px"})])], style={"flex": "1"}),
    ], style={"display": "flex", "gap": "2px", "marginTop": "2px"})

    # ── iperf3 ────────────────────────────────────────────────────────────────
    fig_iperf = make_fig()
    make_line(fig_iperf, df_iperf, "download_mbps", "Download", ACCENT_GREEN)
    make_line(fig_iperf, df_iperf, "upload_mbps",   "Upload",   ACCENT_BLUE)
    fig_iperf.update_layout(yaxis_title="Mbps")
    iperf_server = latest_val(df_iperf, "server") if df_iperf is not None else None
    iperf_panel = chart_panel([
        section_header("IPERF3", f"last server: {iperf_server}" if iperf_server else "every 20 min"),
        dcc.Graph(figure=fig_iperf, config={"displayModeBar": False}, style={"height": "180px"}),
    ])

    # ── curl (light + heavy) ──────────────────────────────────────────────────
    fig_curl_light = make_fig()
    for k in ["hetzner_fsn1", "hetzner_ash", "hetzner_hel1"]:
        tdf = curl_filter(curl_targets, k, 50, 200)
        if tdf is not None and not tdf.empty:
            make_line(fig_curl_light, tdf, "download_mbps", CURL_LABELS.get(k, k), CURL_COLORS.get(k, TEXT_MUTED))
    fig_curl_light.update_layout(yaxis_title="Mbps")

    fig_curl_heavy = make_fig()
    for k in ["hetzner_fsn1", "hetzner_ash", "ubuntu_noble", "eweka"]:
        tdf = curl_filter(curl_targets, k, 201, 9000)
        if tdf is not None and not tdf.empty:
            make_line(fig_curl_heavy, tdf, "download_mbps", CURL_LABELS.get(k, k), CURL_COLORS.get(k, TEXT_MUTED))
    fig_curl_heavy.update_layout(yaxis_title="Mbps")

    stat_configs = [
        ("hetzner_fsn1",  50,  200, "FSN1 100MB"),
        ("hetzner_ash",   50,  200, "ASH 100MB"),
        ("hetzner_hel1",  50,  200, "HEL1 100MB"),
        ("hetzner_fsn1", 201, 2000, "FSN1 1GB"),
        ("hetzner_ash",  201, 2000, "ASH 1GB"),
        ("ubuntu_noble",  50, 9000, "Ubuntu ISO"),
        ("eweka",          0, 9000, "Eweka Usenet"),
    ]
    curl_stats = []
    for k, mn, mx, lbl in stat_configs:
        tdf = curl_filter(curl_targets, k, mn, mx)
        if tdf is None or tdf.empty:
            continue
        lv = tdf["download_mbps"].dropna().iloc[-1] if not tdf["download_mbps"].dropna().empty else None
        av = tdf["download_mbps"].dropna().mean()   if not tdf["download_mbps"].dropna().empty else None
        curl_stats.append(stat_card(lbl.upper(), fmt(lv), "Mbps",
                                    CURL_COLORS.get(k, TEXT_MUTED), sub=f"avg: {fmt(av)} Mbps"))

    curl_panel = chart_panel([
        section_header("CURL DOWNLOAD TARGETS", "real files / no disk write"),
        html.Div(curl_stats, style={"display": "flex", "gap": "2px", "marginBottom": "12px", "flexWrap": "wrap"}),
        html.Div([
            html.Div([
                html.Div("100 MB — 3× routing paths", style={"fontFamily": FONT_MONO, "fontSize": "10px", "color": TEXT_DIM, "marginBottom": "6px"}),
                dcc.Graph(figure=fig_curl_light, config={"displayModeBar": False}, style={"height": "200px"}),
            ], style={"flex": "2"}),
            html.Div([
                html.Div("LARGE FILE — sustained throughput + Usenet", style={"fontFamily": FONT_MONO, "fontSize": "10px", "color": TEXT_DIM, "marginBottom": "6px"}),
                dcc.Graph(figure=fig_curl_heavy, config={"displayModeBar": False}, style={"height": "200px"}),
            ], style={"flex": "1"}),
        ], style={"display": "flex", "gap": "16px"}),
    ])

    # ── 10GB superheavy ───────────────────────────────────────────────────────
    fig_sh = make_fig()
    sh_cards = []
    for k, color in [("hetzner_fsn1", ACCENT_GREEN), ("hetzner_ash", ACCENT_BLUE)]:
        if k in curl_superheavy:
            tdf = curl_superheavy[k]
            make_line(fig_sh, tdf, "download_mbps", CURL_LABELS.get(k, k), color, mode="lines+markers")
            lv = tdf["download_mbps"].dropna().iloc[-1] if not tdf["download_mbps"].dropna().empty else None
            av = tdf["download_mbps"].dropna().mean()   if not tdf["download_mbps"].dropna().empty else None
            sh_cards.append(stat_card(f"10GB {CURL_LABELS.get(k,k)}", fmt(lv), "Mbps", color,
                                      sub=f"all-time avg: {fmt(av)} Mbps"))
    fig_sh.update_layout(yaxis_title="Mbps")
    sh_panel = chart_panel([
        section_header("10 GB SUSTAINED DOWNLOAD", "once per day — best-case line speed"),
        html.Div(sh_cards, style={"display": "flex", "gap": "2px", "marginBottom": "12px", "flexWrap": "wrap"}),
        dcc.Graph(figure=fig_sh, config={"displayModeBar": False}, style={"height": "200px"}),
    ])

    # ── 24h averages table ────────────────────────────────────────────────────
    rows = []
    cell = lambda txt, color=TEXT_PRIMARY: html.Td(txt, style={
        "fontFamily": FONT_MONO, "fontSize": "12px", "color": color,
        "padding": "8px 16px", "borderBottom": f"1px solid {BG_PANEL2}",
    })
    for sname, df, dcol, ucol in [
        ("Ookla",    df_ookla, "download_mbps", "upload_mbps"),
        ("Fast.com", df_fast,  "download_mbps", "upload_mbps"),
        ("NDT7",     df_ndt7,  "download_mbps", "upload_mbps"),
        ("iPerf3",   df_iperf, "download_mbps", "upload_mbps"),
    ]:
        a_dl = avg_val(df, dcol, 24)
        a_ul = avg_val(df, ucol, 24)
        p_dl = avg_val(df, dcol,  1)
        sr   = success_rate(df, 24)
        sr_c = ACCENT_GREEN if (sr or 0) >= 95 else (ACCENT_AMBER if (sr or 0) >= 80 else ACCENT_RED)
        rows.append(html.Tr([cell(sname, TEXT_MUTED), cell(fmt(a_dl), ACCENT_GREEN),
                              cell(fmt(a_ul), ACCENT_BLUE), cell(fmt(p_dl), ACCENT_AMBER),
                              cell(fmt(sr, 0) + "%", sr_c)]))
    summary_panel = chart_panel([
        section_header("24-HOUR AVERAGES", "all sources"),
        html.Table([
            html.Thead(html.Tr([
                html.Th(h, style={"fontFamily": FONT_MONO, "fontSize": "10px", "color": TEXT_DIM,
                                  "padding": "6px 16px", "textAlign": "left",
                                  "borderBottom": f"1px solid {BORDER}"})
                for h in ["SOURCE", "AVG DL (Mbps)", "AVG UL (Mbps)", "LAST 1H DL (Mbps)", "SUCCESS RATE 24H"]
            ])),
            html.Tbody(rows),
        ], style={"width": "100%", "borderCollapse": "collapse"}),
    ])

    footer = html.Div([
        html.Span("SIGMON", style={"color": ACCENT_AMBER, "fontFamily": FONT_MONO,
                                    "fontSize": "10px", "letterSpacing": "0.15em"}),
        html.Span(f"  //  LOG DIR: {LOG_DIR}  //  PORT 8050",
                  style={"fontFamily": FONT_MONO, "fontSize": "10px", "color": TEXT_DIM}),
    ], style={"borderTop": f"1px solid {BORDER}", "padding": "12px 0", "marginTop": "20px"})

    return html.Div([
        kpi, ookla_panel, GAP, row_fn, GAP, iperf_panel, GAP,
        curl_panel, GAP, sh_panel,
        html.Div(style={"height": "20px"}),
        summary_panel, footer,
    ], className="panel")

# ---------------------------------------------------------------------------
# Tab: Latency & Routing
# ---------------------------------------------------------------------------

def _tab_latency(dfs):
    df_ping = dfs.get("ping")
    df_dns  = dfs.get("dns")
    df_mtr  = dfs.get("mtr")

    # Group by label
    ping_by_host    = _group_by(df_ping, "host_label")
    dns_by_resolver = _group_by(df_dns,  "resolver")
    mtr_by_label    = _group_by(df_mtr,  "label")

    # ── Ping / loss / jitter ──────────────────────────────────────────────────
    PING_COLORS = {
        "Cloudflare-DNS-JHB": ACCENT_GREEN,
        "Google-DNS":         ACCENT_BLUE,
        "MLab-JHB":           ACCENT_AMBER,
        "JHB-Local":          ACCENT_PURPLE,
    }
    fig_lat = make_fig(); fig_loss = make_fig(); fig_jitter = make_fig()
    ping_cards = []
    for label, color in PING_COLORS.items():
        df_h = ping_by_host.get(label)
        make_line(fig_lat,    df_h, "avg_ms",          label, color)
        make_line(fig_loss,   df_h, "packet_loss_pct", label, color)
        make_line(fig_jitter, df_h, "jitter_ms",       label, color)
        lv   = latest_val(df_h, "avg_ms")
        loss = latest_val(df_h, "packet_loss_pct")
        ping_cards.append(mini_stat(label.replace("-"," "), fmt(lv), "ms",
            ACCENT_GREEN if (lv or 999)<20 else (ACCENT_AMBER if (lv or 999)<60 else ACCENT_RED)))
        ping_cards.append(mini_stat(f"{label[:8]} LOSS", fmt(loss,1), "%",
            ACCENT_GREEN if (loss or 1)<0.5 else (ACCENT_AMBER if (loss or 1)<2 else ACCENT_RED)))
    fig_lat.update_layout(yaxis_title="ms")
    fig_loss.update_layout(yaxis_title="% loss")
    fig_jitter.update_layout(yaxis_title="ms")

    ping_panel = chart_panel([
        section_header("PING / PACKET LOSS / JITTER", "every 20 min"),
        html.Div(ping_cards, style={"display": "flex", "gap": "2px", "marginBottom": "12px", "flexWrap": "wrap"}),
        html.Div([
            html.Div([html.Div("LATENCY (avg ms)",  style={"fontFamily": FONT_MONO, "fontSize": "10px", "color": TEXT_DIM}),
                      dcc.Graph(figure=fig_lat,    config={"displayModeBar": False}, style={"height": "180px"})], style={"flex": "2"}),
            html.Div([html.Div("PACKET LOSS (%)",   style={"fontFamily": FONT_MONO, "fontSize": "10px", "color": TEXT_DIM}),
                      dcc.Graph(figure=fig_loss,   config={"displayModeBar": False}, style={"height": "180px"})], style={"flex": "1"}),
            html.Div([html.Div("JITTER (mdev ms)",  style={"fontFamily": FONT_MONO, "fontSize": "10px", "color": TEXT_DIM}),
                      dcc.Graph(figure=fig_jitter, config={"displayModeBar": False}, style={"height": "180px"})], style={"flex": "1"}),
        ], style={"display": "flex", "gap": "2px"}),
    ])

    # ── DNS ───────────────────────────────────────────────────────────────────
    DNS_COLORS = {"Cloudflare": ACCENT_GREEN, "Google": ACCENT_BLUE, "Quad9": ACCENT_AMBER}
    fig_dns = make_fig()
    dns_cards = []
    for label, color in DNS_COLORS.items():
        df_r = dns_by_resolver.get(label)
        make_line(fig_dns, df_r, "lookup_ms", label, color)
        lv = latest_val(df_r, "lookup_ms")
        dns_cards.append(mini_stat(label, fmt(lv), "ms",
            ACCENT_GREEN if (lv or 999)<50 else (ACCENT_AMBER if (lv or 999)<150 else ACCENT_RED)))
    fig_dns.update_layout(yaxis_title="ms")
    dns_panel = chart_panel([
        section_header("DNS RESOLVER LATENCY", "every 20 min"),
        html.Div(dns_cards, style={"display": "flex", "gap": "2px", "marginBottom": "12px"}),
        dcc.Graph(figure=fig_dns, config={"displayModeBar": False}, style={"height": "160px"}),
    ])

    # ── MTR ───────────────────────────────────────────────────────────────────
    MTR_COLORS = {
        "NAPAfrica-JHB":    ACCENT_GREEN,
        "TENET-JHB":        ACCENT_BLUE,
        "Dota2-CS2-JHB":    ACCENT_AMBER,
        "Valorant-JHB":     ACCENT_PURPLE,
        "AWS-CapeTown":     ACCENT_RED,
        "Netflix-OC-JHB":   ACCENT_GREEN,
        "Seacom-London":    ACCENT_BLUE,
        "AMS-IX-Europe":    ACCENT_AMBER,
        "Cloudflare-DNS":   ACCENT_PURPLE,
        "Google-DNS":       ACCENT_RED,
    }
    fig_mtr_lat  = make_fig()
    fig_mtr_loss = make_fig()
    mtr_cards = []
    for label, color in MTR_COLORS.items():
        df_m = mtr_by_label.get(label)
        if df_m is None:
            continue
        make_line(fig_mtr_lat,  df_m, "avg_ms",   label, color)
        make_line(fig_mtr_loss, df_m, "loss_pct", label, color)
        lv_avg  = latest_val(df_m, "avg_ms")
        lv_loss = latest_val(df_m, "loss_pct")
        mtr_cards.append(mini_stat(label.replace("-"," ").upper(), fmt(lv_avg), "ms",
            ACCENT_GREEN if (lv_avg or 999)<30 else (ACCENT_AMBER if (lv_avg or 999)<80 else ACCENT_RED)))
        mtr_cards.append(mini_stat(f"{label[:10]} LOSS", fmt(lv_loss,1), "%",
            ACCENT_GREEN if (lv_loss or 1)<0.5 else (ACCENT_AMBER if (lv_loss or 1)<2 else ACCENT_RED)))
    fig_mtr_lat.update_layout(yaxis_title="ms")
    fig_mtr_loss.update_layout(yaxis_title="% loss")

    mtr_content = html.Div("No MTR data yet.", style={"fontFamily": FONT_MONO, "fontSize": "11px",
                                                       "color": TEXT_MUTED, "padding": "20px 0"}) \
        if not mtr_cards else html.Div([
            html.Div(mtr_cards, style={"display": "flex", "gap": "2px", "marginBottom": "12px", "flexWrap": "wrap"}),
            html.Div([
                html.Div([html.Div("AVG LATENCY (ms)",  style={"fontFamily": FONT_MONO, "fontSize": "10px", "color": TEXT_DIM}),
                          dcc.Graph(figure=fig_mtr_lat,  config={"displayModeBar": False}, style={"height": "200px"})], style={"flex": "2"}),
                html.Div([html.Div("PACKET LOSS (%)",    style={"fontFamily": FONT_MONO, "fontSize": "10px", "color": TEXT_DIM}),
                          dcc.Graph(figure=fig_mtr_loss, config={"displayModeBar": False}, style={"height": "200px"})], style={"flex": "1"}),
            ], style={"display": "flex", "gap": "2px"}),
        ])

    mtr_panel = chart_panel([
        section_header("MTR — PATH LATENCY & LOSS", "every 20 min"),
        mtr_content,
    ])

    return html.Div([ping_panel, GAP, dns_panel, GAP, mtr_panel], className="panel")

# ---------------------------------------------------------------------------
# Tab: ISP & Health
# ---------------------------------------------------------------------------

def _tab_isp(dfs_full, dfs_filtered):
    ookla = dfs_full.get("ookla")
    fast  = dfs_full.get("fast")
    ping  = dfs_full.get("ping")

    # ── Health score ──────────────────────────────────────────────────────────
    score = 100
    if ookla is not None and not ookla.empty:
        dl     = latest_val(ookla, "download_mbps")
        avg_dl = avg_val(ookla, "download_mbps", 24)
        if dl and avg_dl:
            ratio = dl / avg_dl
            if ratio < 0.5:   score -= 20
            elif ratio < 0.8: score -= 10
        sr = success_rate(ookla, 24)
        if sr is not None:
            if sr < 80:   score -= 20
            elif sr < 95: score -= 10
    if fast is not None and not fast.empty:
        bloat = latest_val(fast, "bufferbloat_ms")
        if bloat:
            if bloat > 200:   score -= 15
            elif bloat > 100: score -= 8
    if ping is not None and not ping.empty and "host_label" in ping.columns:
        cf = ping[ping["host_label"] == "Cloudflare-DNS-JHB"]
        if not cf.empty:
            loss = latest_val(cf, "packet_loss_pct")
            if loss:
                if loss > 5:   score -= 20
                elif loss > 1: score -= 10
    score = max(0, min(100, score))
    gauge_color = ACCENT_GREEN if score >= 80 else (ACCENT_AMBER if score >= 50 else ACCENT_RED)

    gauge_fig = go.Figure(go.Indicator(
        mode="gauge+number", value=score,
        number={"font": {"color": gauge_color, "size": 40, "family": FONT_MONO}},
        gauge={
            "axis":  {"range": [0, 100], "tickcolor": TEXT_MUTED},
            "bar":   {"color": gauge_color},
            "bgcolor": "rgba(0,0,0,0)",
            "steps": [
                {"range": [0,  50], "color": f"rgba({_hex_to_rgba(ACCENT_RED,   0.15)})"},
                {"range": [50, 80], "color": f"rgba({_hex_to_rgba(ACCENT_AMBER, 0.15)})"},
                {"range": [80,100], "color": f"rgba({_hex_to_rgba(ACCENT_GREEN, 0.15)})"},
            ],
        },
    ))
    gauge_fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=TEXT_MUTED, family=FONT_MONO),
        height=180, margin=dict(l=20, r=20, t=30, b=10),
    )

    # Score breakdown
    score_label = "EXCELLENT" if score >= 80 else ("DEGRADED" if score >= 50 else "POOR")
    score_color = gauge_color

    isp_name = "Unknown"
    isp_loc  = ""
    if ookla is not None and not ookla.empty and "isp" in ookla.columns:
        isp_name = ookla.iloc[-1]["isp"]
    if ookla is not None and not ookla.empty and "server_location" in ookla.columns:
        isp_loc = ookla.iloc[-1]["server_location"]

    health_panel = chart_panel([
        section_header("CONNECTION HEALTH SCORE"),
        html.Div([
            html.Div([
                dcc.Graph(figure=gauge_fig, config={"displayModeBar": False}),
                html.Div(score_label, style={"fontFamily": FONT_MONO, "fontSize": "12px",
                                              "color": score_color, "textAlign": "center",
                                              "letterSpacing": "0.2em"}),
            ], style={"flex": "1"}),
            html.Div([
                stat_card("ISP",          isp_name,                         "",   ACCENT_BLUE),
                stat_card("TEST SERVER",  isp_loc or "—",                   "",   ACCENT_MUTED if not isp_loc else ACCENT_AMBER),
                stat_card("24H AVG DL",   fmt(avg_val(ookla,"download_mbps",24)), "Mbps", ACCENT_GREEN),
                stat_card("24H AVG UL",   fmt(avg_val(ookla,"upload_mbps",  24)), "Mbps", ACCENT_BLUE),
                stat_card("SUCCESS RATE", fmt(success_rate(ookla, 24), 0),        "%",    gauge_color),
            ], style={"flex": "2", "display": "flex", "flexDirection": "column", "gap": "2px"}),
        ], style={"display": "flex", "gap": "16px", "alignItems": "flex-start"}),
    ])

    # ── Compare panel ─────────────────────────────────────────────────────────
    compare_panel = chart_panel([
        section_header("COMPARE TWO DAYS", "ookla download + upload"),
        html.Div([
            html.Div([
                html.Div("Day A", style={"fontFamily": FONT_MONO, "fontSize": "10px",
                                          "color": TEXT_DIM, "marginBottom": "4px"}),
                dcc.DatePickerSingle(
                    id="date1",
                    date=(datetime.now() - timedelta(days=1)).date(),
                    display_format="YYYY-MM-DD",
                    style={"marginBottom": "8px"},
                ),
            ], style={"marginRight": "24px"}),
            html.Div([
                html.Div("Day B", style={"fontFamily": FONT_MONO, "fontSize": "10px",
                                          "color": TEXT_DIM, "marginBottom": "4px"}),
                dcc.DatePickerSingle(
                    id="date2",
                    date=datetime.now().date(),
                    display_format="YYYY-MM-DD",
                ),
            ]),
        ], style={"display": "flex", "alignItems": "flex-end", "marginBottom": "12px"}),
        dcc.Graph(id="compare-graph", config={"displayModeBar": False}, style={"height": "250px"}),
    ])

    return html.Div([health_panel, GAP, compare_panel], className="panel")

# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _group_by(df, col):
    result = {}
    if df is not None and not df.empty and col in df.columns:
        for label, tdf in df.groupby(col):
            result[label] = tdf.reset_index(drop=True)
    return result

# Patch: ACCENT_MUTED wasn't defined, use TEXT_MUTED as fallback
ACCENT_MUTED = TEXT_MUTED

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=False)
