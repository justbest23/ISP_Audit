#!/usr/bin/env python3
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import pandas as pd
import plotly.graph_objects as go
import os
from datetime import datetime, timedelta

LOG_DIR = "/home/troggoman/speedtests/logs"

# ---------------------------------------------------------------------------
# MTR (PingPlotter-style) Audit Targets
# ---------------------------------------------------------------------------
MTR_TARGETS = [
    ("196.60.8.1",      "NAPAfrica-JHB"),
    ("155.232.0.1",     "TENET-JHB"),
    ("197.80.200.1",    "Dota2-CS2-JHB"),
    ("160.119.102.162", "Valorant-JHB"),
    ("rds.af-south-1.amazonaws.com", "AWS-CapeTown"),
    ("197.221.23.194",  "Netflix-OC-JHB"),
    ("193.58.13.249",   "Seacom-London"),
    ("80.249.208.1",    "AMS-IX-Europe"),
    ("1.1.1.1",         "Cloudflare-DNS"),
    ("8.8.8.8",         "Google-DNS"),
]

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
TEXT_PRIMARY = "#e8edf2"
TEXT_MUTED   = "#b6bfc5"
TEXT_DIM     = "#3ec569"
FONT_MONO    = "'JetBrains Mono', 'Fira Code', 'Courier New', monospace"
FONT_UI      = "'DM Sans', 'Helvetica Neue', sans-serif"
BG_TRANSPARENT = "rgba(0,0,0,0)"

PLOTLY_THEME = {
    "paper_bgcolor": "BG_TRANSPARENT",
    "plot_bgcolor": "BG_TRANSPARENT",
    "font": {"family": FONT_MONO, "color": TEXT_MUTED, "size": 11},
    "xaxis": {"gridcolor": BG_PANEL2, "linecolor": BORDER, "tickcolor": TEXT_DIM, "zeroline": False},
    "yaxis": {"gridcolor": BG_PANEL2, "linecolor": BORDER, "tickcolor": TEXT_DIM, "zeroline": False},
    "legend": {"bgcolor": "BG_TRANSPARENT", "bordercolor": BORDER, "borderwidth": 1, "font": {"size": 10}},
    "margin": {"l": 48, "r": 16, "t": 16, "b": 40},
    "hovermode": "x unified",
    "hoverlabel": {"bgcolor": BG_PANEL2, "bordercolor": BORDER,
                    "font": {"family": FONT_MONO, "size": 11, "color": TEXT_PRIMARY}},
}

PING_COLORS = {
    "Cloudflare-DNS-JHB": ACCENT_GREEN,
    "Google-DNS":         ACCENT_BLUE,
    "MLab-JHB":           ACCENT_AMBER,
    "JHB-Local":          ACCENT_PURPLE,
}

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

def latest_val(df, col):
    if df is None or col not in df.columns:
        return None
    vals = df[col].dropna()
    return vals.iloc[-1] if not vals.empty else None

def avg_val(df, col, hours=24):
    if df is None or col not in df.columns:
        return None
    cutoff = datetime.now() - timedelta(hours=hours)
    recent = df[df["timestamp"] > cutoff][col].dropna()
    return recent.mean() if not recent.empty else None

def success_rate(df, hours=24):
    if df is None or "status" not in df.columns:
        return None
    cutoff = datetime.now() - timedelta(hours=hours)
    recent = df[df["timestamp"] > cutoff]
    return (recent["status"] == "success").mean() * 100 if not recent.empty else None

def fmt(val, decimals=1, suffix=""):
    return "—" if val is None else f"{val:.{decimals}f}{suffix}"

def make_line(fig, df, col, name, color, dash="solid", mode="lines"):
    if df is None or col not in df.columns:
        return
    d = df[["timestamp", col]].dropna()
    fig.add_trace(go.Scatter(
        x=d["timestamp"], y=d[col], name=name, mode=mode,
        line={"color": color, "width": 1.5, "dash": dash},
        hovertemplate=f"%{{y:.1f}}<extra>{name}</extra>",
    ))

def make_fig():
    fig = go.Figure()
    fig.update_layout(**PLOTLY_THEME)
    return fig

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
# App
# ---------------------------------------------------------------------------

app = dash.Dash(__name__, title="SIGMON // Speed Monitor")

## ChatGPT Additions ##
server = app.server
app.config.suppress_callback_exceptions = True # Needed for dynamic MTR Dropdown
###

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
        .dash-dropdown .Select-control { background-color: #131920; border: 1px solid #1e2a35; color: #e8edf2; }
        .dash-dropdown .Select-value-label { color: #e8edf2 !important; }
        .dash-dropdown .Select-menu-outer { background-color: #131920; border: 1px solid #1e2a35; }
        .dash-dropdown .VirtualizedSelectOption { background-color: #131920; color: #e8edf2; }
        .dash-dropdown .VirtualizedSelectFocusedOption { background-color: #1e2a35; }
    </style>
</head>
<body>{%app_entry%}<footer>{%config%}{%scripts%}{%renderer%}</footer>
</body>
</html>
'''

app.layout = html.Div([
    dcc.Interval(id="tick", interval=120_000, n_intervals=0),

    # Header
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
            html.Span(" | AUTO-REFRESH 120s", style={"fontFamily": FONT_MONO, "fontSize": "10px",
                                                       "color": TEXT_DIM, "marginLeft": "12px"}),
        ], style={"display": "flex", "alignItems": "center"}),
    ], style={
        "display": "flex", "justifyContent": "space-between", "alignItems": "center",
        "padding": "16px 24px", "borderBottom": f"1px solid {BORDER}",
        "backgroundColor": BG_PANEL, "position": "sticky", "top": "0", "zIndex": "100",
    }),

    html.Div([html.Div(id="dashboard-content")],
             style={"padding": "20px 24px", "maxWidth": "1600px", "margin": "0 auto"}),
], style={"backgroundColor": BG_PAGE, "minHeight": "100vh"})

# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

@app.callback(Output("header-time", "children"), Input("tick", "n_intervals"))
def update_clock(n):
    return datetime.now().strftime("%Y-%m-%d  %H:%M:%S")


def _load_all_data():
    """Load all CSV data sources."""
    return {
        "ookla": load_csv("ookla.csv"),
        "fast": load_csv("fast.csv"),
        "iperf": load_csv("iperf3.csv"),
        "ndt7": load_csv("ndt7.csv"),
        "curl": load_csv("curl.csv"),
        "ping": load_csv("ping.csv"),
        "dns": load_csv("dns.csv"),
        "mtr": load_csv("mtr.csv"),
    }

def _split_curl_data(df_curl):
    """Split curl data by target and size."""
    curl_targets = {}
    curl_superheavy = {}
    if df_curl is not None and "target_name" in df_curl.columns:
        for tname, tdf in df_curl.groupby("target_name"):
            curl_targets[tname] = tdf.reset_index(drop=True)
    if df_curl is not None and "file_size_mb" in df_curl.columns:
        sh = df_curl[df_curl["file_size_mb"] >= 9000]
        for tname, tdf in sh.groupby("target_name"):
            curl_superheavy[tname] = tdf.reset_index(drop=True)
    return curl_targets, curl_superheavy

def _split_ping_data(df_ping):
    """Split ping data by host_label."""
    ping_by_host = {}
    if df_ping is not None and "host_label" in df_ping.columns:
        for label, tdf in df_ping.groupby("host_label"):
            ping_by_host[label] = tdf.reset_index(drop=True)
    return ping_by_host

def _split_dns_data(df_dns):
    """Split DNS data by resolver."""
    dns_by_resolver = {}
    if df_dns is not None and "resolver" in df_dns.columns:
        for label, tdf in df_dns.groupby("resolver"):
            dns_by_resolver[label] = tdf.reset_index(drop=True)
    return dns_by_resolver

def _build_kpi_strip(df_ookla, df_fast, df_ndt7, ping_by_host):
    """Build KPI strip with key metrics."""
    ookla_dl  = latest_val(df_ookla, "download_mbps")
    ookla_ul  = latest_val(df_ookla, "upload_mbps")
    ookla_png = latest_val(df_ookla, "ping_ms")
    avg_dl    = avg_val(df_ookla, "download_mbps", 24)
    avg_ul    = avg_val(df_ookla, "upload_mbps",   24)
    sr_ookla  = success_rate(df_ookla, 24)
    bloat     = latest_val(df_fast, "bufferbloat_ms")
    cf_ping   = latest_val(ping_by_host.get("Cloudflare-DNS-JHB"), "avg_ms")
    cf_loss   = latest_val(ping_by_host.get("Cloudflare-DNS-JHB"), "packet_loss_pct")

    return html.Div([
        stat_card("DOWNLOAD",      fmt(ookla_dl),  "Mbps", ACCENT_GREEN,
                  sub=f"24h avg: {fmt(avg_dl)} Mbps"),
        stat_card("UPLOAD",        fmt(ookla_ul),  "Mbps", ACCENT_BLUE,
                  sub=f"24h avg: {fmt(avg_ul)} Mbps"),
        stat_card("PING",          fmt(ookla_png), "ms",   ACCENT_AMBER),
        stat_card("CF LATENCY",    fmt(cf_ping),   "ms",   ACCENT_AMBER,
                  sub=f"loss: {fmt(cf_loss, 1)}%"),
        stat_card("BUFFERBLOAT",   fmt(bloat),     "ms",
                  ACCENT_GREEN if (bloat or 999) < 50 else (ACCENT_AMBER if (bloat or 999) < 100 else ACCENT_RED)),
        stat_card("NDT7 DL",       fmt(latest_val(df_ndt7, "download_mbps")), "Mbps", ACCENT_PURPLE),
        stat_card("OOKLA SUCCESS", fmt(sr_ookla, 0), "%",
                  ACCENT_GREEN if (sr_ookla or 0) >= 90 else ACCENT_RED),
    ], style={"display": "flex", "gap": "2px", "marginBottom": "20px", "flexWrap": "wrap"})

def _build_ookla_panel(df_ookla):
    """Build Ookla speedtest panel."""
    fig_ookla = make_fig()
    make_line(fig_ookla, df_ookla, "download_mbps", "Download", ACCENT_GREEN)
    make_line(fig_ookla, df_ookla, "upload_mbps",   "Upload",   ACCENT_BLUE)
    fig_ookla.update_layout(yaxis_title="Mbps")

    fig_ping_ookla = make_fig()
    make_line(fig_ping_ookla, df_ookla, "ping_ms", "Ping", ACCENT_AMBER)
    fig_ping_ookla.update_layout(yaxis_title="ms")

    return chart_panel([
        section_header("OOKLA SPEEDTEST", "every 20 min"),
        html.Div([
            html.Div([dcc.Graph(figure=fig_ookla, config={"displayModeBar": False},
                                style={"height": "200px"})], style={"flex": "2"}),
            html.Div([dcc.Graph(figure=fig_ping_ookla, config={"displayModeBar": False},
                                style={"height": "200px"})], style={"flex": "1"}),
        ], style={"display": "flex", "gap": "2px"}),
    ])

def _build_fast_ndt7_row(df_fast, df_ndt7):
    """Build fast.com and NDT7 comparison row."""
    fig_fast = make_fig()
    make_line(fig_fast, df_fast, "download_mbps",  "Download",   ACCENT_GREEN)
    make_line(fig_fast, df_fast, "upload_mbps",    "Upload",     ACCENT_BLUE)
    make_line(fig_fast, df_fast, "latency_ms",     "Latency",    ACCENT_AMBER, dash="dot")
    make_line(fig_fast, df_fast, "bufferbloat_ms", "Bufferbloat",ACCENT_RED,   dash="dash")
    fig_fast.update_layout(yaxis_title="Mbps / ms")

    fig_ndt7 = make_fig()
    make_line(fig_ndt7, df_ndt7, "download_mbps", "Download", ACCENT_GREEN)
    make_line(fig_ndt7, df_ndt7, "upload_mbps",   "Upload",   ACCENT_BLUE)
    make_line(fig_ndt7, df_ndt7, "rtt_ms",        "RTT",      ACCENT_AMBER, dash="dot")
    fig_ndt7.update_layout(yaxis_title="Mbps / ms")

    return html.Div([
        html.Div([chart_panel([
            section_header("FAST.COM", "every 20 min"),
            dcc.Graph(figure=fig_fast, config={"displayModeBar": False}, style={"height": "200px"}),
        ])], style={"flex": "1"}),
        html.Div([chart_panel([
            section_header("NDT7", "every 20 min"),
            dcc.Graph(figure=fig_ndt7, config={"displayModeBar": False}, style={"height": "200px"}),
        ])], style={"flex": "1"}),
    ], style={"display": "flex", "gap": "2px", "marginTop": "2px"})

def _build_iperf_panel(df_iperf):
    """Build iPerf3 panel."""
    fig_iperf = make_fig()
    make_line(fig_iperf, df_iperf, "download_mbps", "Download", ACCENT_GREEN)
    make_line(fig_iperf, df_iperf, "upload_mbps",   "Upload",   ACCENT_BLUE)
    fig_iperf.update_layout(yaxis_title="Mbps")

    iperf_server = latest_val(df_iperf, "server") if df_iperf is not None and "server" in (df_iperf.columns if df_iperf is not None else []) else None
    iperf_tag = f"last server: {iperf_server}" if iperf_server else "every 20 min"

    return chart_panel([
        section_header("IPERF3", iperf_tag),
        dcc.Graph(figure=fig_iperf, config={"displayModeBar": False}, style={"height": "180px"}),
    ])

def _ping_accent(val, low, med, missing=999):
    return ACCENT_GREEN if (val or missing) < low else (
        ACCENT_AMBER if (val or missing) < med else ACCENT_RED
    )


def _build_ping_figures(ping_by_host):
    fig_latency = make_fig()
    fig_loss    = make_fig()
    fig_jitter  = make_fig()

    for label, color in PING_COLORS.items():
        df_h = ping_by_host.get(label)
        if df_h is None:
            continue
        make_line(fig_latency, df_h, "avg_ms",          label, color)
        make_line(fig_loss,    df_h, "packet_loss_pct", label, color)
        make_line(fig_jitter,  df_h, "jitter_ms",       label, color)

    fig_latency.update_layout(yaxis_title="ms")
    fig_loss.update_layout(yaxis_title="% loss")
    fig_jitter.update_layout(yaxis_title="ms")
    return fig_latency, fig_loss, fig_jitter


def _build_ping_cards(ping_by_host):
    cards = []
    for label in PING_COLORS:
        df_h = ping_by_host.get(label)
        lv = latest_val(df_h, "avg_ms")
        loss = latest_val(df_h, "packet_loss_pct")
        cards.append(mini_stat(
            label.replace("-", " "),
            fmt(lv), "ms",
            _ping_accent(lv, 20, 60)
        ))
        cards.append(mini_stat(
            f"{label[:8]} LOSS",
            fmt(loss, 1), "%",
            _ping_accent(loss, 0.5, 2, missing=1)
        ))
    return cards


def _build_ping_panel(ping_by_host):
    """Build ping, packet loss and jitter panel."""
    fig_latency, fig_loss, fig_jitter = _build_ping_figures(ping_by_host)
    ping_cards = _build_ping_cards(ping_by_host)

    return chart_panel([
        section_header("PING / PACKET LOSS / JITTER", "every 20 min"),
        html.Div(ping_cards, style={"display": "flex", "gap": "2px", "marginBottom": "12px", "flexWrap": "wrap"}),
        html.Div([
            html.Div([
                html.Div("LATENCY (avg ms)", style={"fontFamily": FONT_MONO, "fontSize": "10px",
                                                     "color": TEXT_DIM, "marginBottom": "4px"}),
                dcc.Graph(figure=fig_latency, config={"displayModeBar": False}, style={"height": "180px"}),
            ], style={"flex": "2"}),
            html.Div([
                html.Div("PACKET LOSS (%)", style={"fontFamily": FONT_MONO, "fontSize": "10px",
                                                    "color": TEXT_DIM, "marginBottom": "4px"}),
                dcc.Graph(figure=fig_loss, config={"displayModeBar": False}, style={"height": "180px"}),
            ], style={"flex": "1"}),
            html.Div([
                html.Div("JITTER (mdev ms)", style={"fontFamily": FONT_MONO, "fontSize": "10px",
                                                     "color": TEXT_DIM, "marginBottom": "4px"}),
                dcc.Graph(figure=fig_jitter, config={"displayModeBar": False}, style={"height": "180px"}),
            ], style={"flex": "1"}),
        ], style={"display": "flex", "gap": "2px"}),
    ])

def _build_mtr_panel(df_mtr, mtr_target):
    """Build MTR routing audit panel."""
    mtr_content = html.Div("No MTR data available for this target.", style={"color": TEXT_DIM, "fontFamily": FONT_MONO})
    
    if df_mtr is not None and "label" in df_mtr.columns:
        df_t = df_mtr[df_mtr["label"] == mtr_target]
        if not df_t.empty:
            latest_ts = df_t["timestamp"].max()
            current_hops = df_t[df_t["timestamp"] == latest_ts]
            
            if "hop" in current_hops.columns:
                current_hops = current_hops.sort_values("hop")
            
            rows = []
            for idx, row in current_hops.iterrows():
                lat_color = ACCENT_RED if row.get('avg_ms', 0) > 150 else (ACCENT_AMBER if row.get('avg_ms', 0) > 50 else TEXT_PRIMARY)
                loss_color = ACCENT_RED if row.get('loss_pct', 0) > 0 else TEXT_DIM
                
                rows.append(html.Tr([
                    html.Td(f"#{row.get('hop', '?')}", style={"color": TEXT_DIM, "padding": "6px 16px", "fontFamily": FONT_MONO, "fontSize": "11px", "borderBottom": f"1px solid {BORDER}"}),
                    html.Td(row.get('host', ''), style={"color": TEXT_PRIMARY, "padding": "6px 16px", "fontFamily": FONT_MONO, "fontSize": "11px", "borderBottom": f"1px solid {BORDER}"}),
                    html.Td(fmt(row.get('avg_ms')), style={"color": lat_color, "padding": "6px 16px", "fontFamily": FONT_MONO, "fontSize": "11px", "borderBottom": f"1px solid {BORDER}"}),
                    html.Td(fmt(row.get('loss_pct'), 1) + "%", style={"color": loss_color, "padding": "6px 16px", "fontFamily": FONT_MONO, "fontSize": "11px", "borderBottom": f"1px solid {BORDER}"}),
                    html.Td(fmt(row.get('jitter_ms')), style={"color": TEXT_DIM, "padding": "6px 16px", "fontFamily": FONT_MONO, "fontSize": "11px", "borderBottom": f"1px solid {BORDER}"}),
                ]))

            mtr_content = html.Table([
                html.Thead(html.Tr([
                    html.Th(h, style={"fontFamily": FONT_MONO, "fontSize": "9px", "color": TEXT_DIM, "textAlign": "left", "padding": "4px 16px", "borderBottom": f"1px solid {BORDER}"}) 
                    for h in ["HOP", "HOST", "AVG (ms)", "LOSS", "JITTER"]
                ])),
                html.Tbody(rows)
            ], style={"width": "100%", "borderCollapse": "collapse"})

    return chart_panel([
        html.Div([
            section_header("MTR ROUTING AUDIT", mtr_target),
            dcc.Dropdown(
                id="mtr-target-selector",
                options=[{"label": name, "value": name} for addr, name in MTR_TARGETS],
                value=mtr_target,
                clearable=False,
                className="dash-dropdown",
                style={
                    "backgroundColor": BG_PANEL2, "color": "#000", "width": "250px",
                    "fontFamily": FONT_MONO, "fontSize": "11px", "border": f"1px solid {BORDER}"
                }
            )
        ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "flex-start", "marginBottom": "15px"}),
        mtr_content
    ])

def _build_dns_panel(dns_by_resolver):
    """Build DNS resolver latency panel."""
    DNS_COLORS = {"Cloudflare": ACCENT_GREEN, "Google": ACCENT_BLUE, "Quad9": ACCENT_AMBER}
    fig_dns = make_fig()
    for label, color in DNS_COLORS.items():
        df_r = dns_by_resolver.get(label)
        make_line(fig_dns, df_r, "lookup_ms", label, color)
    fig_dns.update_layout(yaxis_title="ms")

    dns_cards = []
    for label, color in DNS_COLORS.items():
        df_r = dns_by_resolver.get(label)
        lv   = latest_val(df_r, "lookup_ms")
        dns_cards.append(mini_stat(label, fmt(lv), "ms",
            ACCENT_GREEN if (lv or 999) < 50 else (ACCENT_AMBER if (lv or 999) < 150 else ACCENT_RED)))

    return chart_panel([
        section_header("DNS RESOLVER LATENCY", "every 20 min"),
        html.Div(dns_cards, style={"display": "flex", "gap": "2px", "marginBottom": "12px"}),
        dcc.Graph(figure=fig_dns, config={"displayModeBar": False}, style={"height": "160px"}),
    ])

def _build_curl_panel(curl_targets):
    """Build curl download targets panel."""
    CURL_COLORS = {
        "hetzner_fsn1": ACCENT_GREEN,
        "hetzner_ash":  ACCENT_BLUE,
        "hetzner_hel1": ACCENT_AMBER,
        "ubuntu_noble": ACCENT_PURPLE,
    }
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

    light_keys  = ["hetzner_fsn1", "hetzner_ash", "hetzner_hel1"]
    heavy_keys  = ["hetzner_fsn1", "hetzner_ash", "ubuntu_noble"]

    fig_curl_light = make_fig()
    for k in light_keys:
        tdf = curl_filter(k, 50, 200)
        if tdf is None or tdf.empty:
            continue
        fig_curl_light.add_trace(go.Scatter(
            x=tdf["timestamp"], y=tdf["download_mbps"],
            name=CURL_LABELS.get(k, k), mode="lines",
            line=dict(color=CURL_COLORS.get(k, TEXT_MUTED), width=1.5),
            hovertemplate="%{y:.1f} Mbps<extra>" + CURL_LABELS.get(k, k) + "</extra>",
        ))
    fig_curl_light.update_layout(yaxis_title="Mbps")

    fig_curl_heavy = make_fig()
    for k in heavy_keys:
        tdf = curl_filter(k, 201, 9000)
        if tdf is None or tdf.empty:
            continue
        fig_curl_heavy.add_trace(go.Scatter(
            x=tdf["timestamp"], y=tdf["download_mbps"],
            name=CURL_LABELS.get(k, k), mode="lines+markers",
            marker=dict(size=5, color=CURL_COLORS.get(k, TEXT_MUTED)),
            line=dict(color=CURL_COLORS.get(k, TEXT_MUTED), width=1.5),
            hovertemplate="%{y:.1f} Mbps<extra>" + CURL_LABELS.get(k, k) + "</extra>",
        ))
    fig_curl_heavy.update_layout(yaxis_title="Mbps")

    curl_stats = []
    stat_configs = [
        ("hetzner_fsn1",  50,  200),
        ("hetzner_ash",   50,  200),
        ("hetzner_hel1",  50,  200),
        ("hetzner_fsn1", 201, 2000),
        ("hetzner_ash",  201, 2000),
        ("ubuntu_noble",  50, 9000),
    ]
    stat_labels = {
        ("hetzner_fsn1",  50,  200): "FSN1 100MB",
        ("hetzner_ash",   50,  200): "ASH 100MB",
        ("hetzner_hel1",  50,  200): "HEL1 100MB",
        ("hetzner_fsn1", 201, 2000): "FSN1 1GB",
        ("hetzner_ash",  201, 2000): "ASH 1GB",
        ("ubuntu_noble",  50, 9000): "Ubuntu ISO",
    }
    for (k, mn, mx) in stat_configs:
        tdf = curl_filter(k, mn, mx)
        if tdf is None or tdf.empty:
            continue
        lv = tdf["download_mbps"].dropna().iloc[-1] if not tdf["download_mbps"].dropna().empty else None
        av = tdf["download_mbps"].dropna().mean()   if not tdf["download_mbps"].dropna().empty else None
        curl_stats.append(stat_card(
            stat_labels[(k, mn, mx)].upper(), fmt(lv), "Mbps",
            CURL_COLORS.get(k, TEXT_MUTED), sub=f"avg: {fmt(av)} Mbps",
        ))

    return chart_panel([
        section_header("CURL DOWNLOAD TARGETS", "real files / no disk write"),
        html.Div(curl_stats, style={"display": "flex", "gap": "2px", "marginBottom": "12px", "flexWrap": "wrap"}),
        html.Div([
            html.Div([
                html.Div("100 MB — 3× routing paths", style={"fontFamily": FONT_MONO,
                    "fontSize": "10px", "color": TEXT_DIM, "marginBottom": "6px"}),
                dcc.Graph(figure=fig_curl_light, config={"displayModeBar": False}, style={"height": "200px"}),
            ], style={"flex": "2"}),
            html.Div([
                html.Div("LARGE FILE — sustained throughput", style={"fontFamily": FONT_MONO,
                    "fontSize": "10px", "color": TEXT_DIM, "marginBottom": "6px"}),
                dcc.Graph(figure=fig_curl_heavy, config={"displayModeBar": False}, style={"height": "200px"}),
            ], style={"flex": "1"}),
        ], style={"display": "flex", "gap": "16px"}),
    ])

def _build_superheavy_panel(curl_superheavy):
    """Build 10GB sustained download panel."""
    fig_sh = make_fig()
    sh_cards = []
    for k, color in [("hetzner_fsn1", ACCENT_GREEN), ("hetzner_ash", ACCENT_BLUE)]:
        if k in curl_superheavy:
            tdf = curl_superheavy[k]
            fig_sh.add_trace(go.Scatter(
                x=tdf["timestamp"], y=tdf["download_mbps"],
                name={"hetzner_fsn1": "Hetzner FSN1 (Frankfurt)", "hetzner_ash": "Hetzner ASH (Ashburn)"}.get(k, k), mode="lines+markers",
                marker=dict(size=6, color=color),
                line=dict(color=color, width=2),
                hovertemplate="%{y:.1f} Mbps<extra>" + {"hetzner_fsn1": "Hetzner FSN1 (Frankfurt)", "hetzner_ash": "Hetzner ASH (Ashburn)"}.get(k, k) + "</extra>",
            ))
            lv = tdf["download_mbps"].dropna().iloc[-1] if not tdf["download_mbps"].dropna().empty else None
            av = tdf["download_mbps"].dropna().mean()   if not tdf["download_mbps"].dropna().empty else None
            server_name = {"hetzner_fsn1": "Hetzner FSN1 (Frankfurt)", "hetzner_ash": "Hetzner ASH (Ashburn)"}.get(k, k)
            sh_cards.append(stat_card(
                f"10GB  {server_name}", fmt(lv), "Mbps", color, sub=f"all-time avg: {fmt(av)} Mbps",))
    fig_sh.update_layout(yaxis_title="Mbps")

    return chart_panel([
        section_header("10 GB SUSTAINED DOWNLOAD", "once per day — best-case line speed"),
        html.Div(sh_cards, style={"display": "flex", "gap": "2px", "marginBottom": "12px", "flexWrap": "wrap"}),
        dcc.Graph(figure=fig_sh, config={"displayModeBar": False}, style={"height": "200px"}),
    ])

def _build_summary_panel(df_ookla, df_fast, df_ndt7, df_iperf):
    """Build 24-hour averages summary panel."""
    rows = []
    sources = [
        ("Ookla",    df_ookla, "download_mbps", "upload_mbps"),
        ("Fast.com", df_fast,  "download_mbps", "upload_mbps"),
        ("NDT7",     df_ndt7,  "download_mbps", "upload_mbps"),
        ("iPerf3",   df_iperf, "download_mbps", "upload_mbps"),
    ]
    cell_fn = lambda txt, color=TEXT_PRIMARY: html.Td(txt, style={
        "fontFamily": FONT_MONO, "fontSize": "12px", "color": color,
        "padding": "8px 16px", "borderBottom": f"1px solid {BG_PANEL2}",
    })
    for sname, df, dcol, ucol in sources:
        a_dl = avg_val(df, dcol, 24)
        a_ul = avg_val(df, ucol, 24)
        p_dl = avg_val(df, dcol,  1)
        sr   = success_rate(df, 24)
        sr_color = ACCENT_GREEN if (sr or 0) >= 95 else (ACCENT_AMBER if (sr or 0) >= 80 else ACCENT_RED)
        rows.append(html.Tr([
            cell_fn(sname, TEXT_MUTED),
            cell_fn(fmt(a_dl), ACCENT_GREEN),
            cell_fn(fmt(a_ul), ACCENT_BLUE),
            cell_fn(fmt(p_dl), ACCENT_AMBER),
            cell_fn(fmt(sr, 0) + "%", sr_color),
        ]))

    return chart_panel([
        section_header("24-HOUR AVERAGES", "all sources"),
        html.Table([
            html.Thead(html.Tr([
                html.Th(h, style={
                    "fontFamily": FONT_MONO, "fontSize": "10px", "color": TEXT_DIM,
                    "padding": "6px 16px", "textAlign": "left", "letterSpacing": "0.1em",
                    "borderBottom": f"1px solid {BORDER}",
                }) for h in ["SOURCE", "AVG DL (Mbps)", "AVG UL (Mbps)", "LAST 1H DL (Mbps)", "SUCCESS RATE 24H"]
            ])),
            html.Tbody(rows),
        ], style={"width": "100%", "borderCollapse": "collapse"}),
    ])

@app.callback(
    Output("dashboard-content", "children"),
    [Input("tick", "n_intervals"),
     Input("mtr-target-selector", "value")]
)
def update_dashboard(n, mtr_target):
    mtr_target = mtr_target or "NAPAfrica-JHB"

    data = _load_all_data()
    df_ookla, df_fast, df_iperf, df_ndt7, df_curl = data["ookla"], data["fast"], data["iperf"], data["ndt7"], data["curl"]
    df_ping, df_dns, df_mtr = data["ping"], data["dns"], data["mtr"]

    curl_targets, curl_superheavy = _split_curl_data(df_curl)
    ping_by_host = _split_ping_data(df_ping)
    dns_by_resolver = _split_dns_data(df_dns)

    kpi_strip = _build_kpi_strip(df_ookla, df_fast, df_ndt7, ping_by_host)
    ookla_panel = _build_ookla_panel(df_ookla)
    row_fast_ndt7 = _build_fast_ndt7_row(df_fast, df_ndt7)
    iperf_panel = _build_iperf_panel(df_iperf)
    ping_panel = _build_ping_panel(ping_by_host)
    mtr_panel = _build_mtr_panel(df_mtr, mtr_target)
    dns_panel = _build_dns_panel(dns_by_resolver)
    curl_panel = _build_curl_panel(curl_targets)
    sh_panel = _build_superheavy_panel(curl_superheavy)
    summary_panel = _build_summary_panel(df_ookla, df_fast, df_ndt7, df_iperf)

    # ── KPI strip ────────────────────────────────────────────────────────────
    ookla_dl  = latest_val(df_ookla, "download_mbps")
    ookla_ul  = latest_val(df_ookla, "upload_mbps")
    ookla_png = latest_val(df_ookla, "ping_ms")
    avg_dl    = avg_val(df_ookla, "download_mbps", 24)
    avg_ul    = avg_val(df_ookla, "upload_mbps",   24)
    sr_ookla  = success_rate(df_ookla, 24)
    bloat     = latest_val(df_fast, "bufferbloat_ms")
    cf_ping   = latest_val(ping_by_host.get("Cloudflare-DNS-JHB"), "avg_ms")
    cf_loss   = latest_val(ping_by_host.get("Cloudflare-DNS-JHB"), "packet_loss_pct")

    kpi_strip = html.Div([
        stat_card("DOWNLOAD",      fmt(ookla_dl),  "Mbps", ACCENT_GREEN,
                  sub=f"24h avg: {fmt(avg_dl)} Mbps"),
        stat_card("UPLOAD",        fmt(ookla_ul),  "Mbps", ACCENT_BLUE,
                  sub=f"24h avg: {fmt(avg_ul)} Mbps"),
        stat_card("PING",          fmt(ookla_png), "ms",   ACCENT_AMBER),
        stat_card("CF LATENCY",    fmt(cf_ping),   "ms",   ACCENT_AMBER,
                  sub=f"loss: {fmt(cf_loss, 1)}%"),
        stat_card("BUFFERBLOAT",   fmt(bloat),     "ms",
                  ACCENT_GREEN if (bloat or 999) < 50 else (ACCENT_AMBER if (bloat or 999) < 100 else ACCENT_RED)),
        stat_card("NDT7 DL",       fmt(latest_val(df_ndt7, "download_mbps")), "Mbps", ACCENT_PURPLE),
        stat_card("OOKLA SUCCESS", fmt(sr_ookla, 0), "%",
                  ACCENT_GREEN if (sr_ookla or 0) >= 90 else ACCENT_RED),
    ], style={"display": "flex", "gap": "2px", "marginBottom": "20px", "flexWrap": "wrap"})

    footer = html.Div([
        html.Span("SIGMON", style={"color": ACCENT_AMBER, "fontFamily": FONT_MONO,
                                    "fontSize": "10px", "letterSpacing": "0.15em"}),
        html.Span(f"  //  LOG DIR: {LOG_DIR}  //  PORT 8050", style={
            "fontFamily": FONT_MONO, "fontSize": "10px", "color": TEXT_DIM,
        }),
    ], style={"borderTop": f"1px solid {BORDER}", "padding": "12px 0", "marginTop": "20px"})

    return html.Div([
        kpi_strip, ookla_panel, GAP, row_fast_ndt7, GAP, iperf_panel, GAP,
        ping_panel, GAP, mtr_panel, GAP,
        html.Div([html.Div([dns_panel], style={"flex": "1"})], style={"display": "flex", "gap": "2px", "marginTop": "2px"}),
        GAP, curl_panel, GAP, sh_panel, html.Div(style={"height": "20px"}),
        summary_panel, footer,
    ], className="panel")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=False)