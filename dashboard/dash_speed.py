#!/usr/bin/env python3
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import pandas as pd
import plotly.graph_objects as go
import os
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Config & Paths
# ---------------------------------------------------------------------------
LOG_DIR = "/home/troggoman/speedtests/logs"

# Defined targets for the MTR dropdown
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
# Design tokens
# ---------------------------------------------------------------------------
BG_PAGE      = "#0a0c0f"
BG_PANEL     = "#0f1318"
BORDER       = "#1e2a35"
ACCENT_AMBER = "#f0a500"
ACCENT_GREEN = "#39d98a"
ACCENT_BLUE  = "#3fa9f5"
ACCENT_RED   = "#f05454"
TEXT_PRIMARY = "#e8edf2"
TEXT_DIM     = "#3ec569"
TEXT_MUTED   = "#b6bfc5"
FONT_MONO    = "'JetBrains Mono', 'Fira Code', 'Courier New', monospace"

# ---------------------------------------------------------------------------
# Data Helpers
# ---------------------------------------------------------------------------
def load_csv(name):
    path = os.path.join(LOG_DIR, name)
    if not os.path.exists(path): return None
    try:
        df = pd.read_csv(path)
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df
    except: return None

def fmt(val, precision=2):
    try: return f"{float(val):.{precision}f}"
    except: return "0.00"

# ---------------------------------------------------------------------------
# UI Components
# ---------------------------------------------------------------------------
def section_header(title, subtitle=""):
    return html.Div([
        html.Div(title, style={"color": ACCENT_AMBER, "fontFamily": FONT_MONO, "fontSize": "14px", "fontWeight": "bold", "letterSpacing": "0.1em"}),
        html.Div(subtitle, style={"color": TEXT_MUTED, "fontSize": "10px", "marginTop": "2px", "fontFamily": FONT_MONO})
    ], style={"marginBottom": "15px", "borderLeft": f"3px solid {ACCENT_AMBER}", "paddingLeft": "12px"})

def chart_panel(children):
    return html.Div(children, style={"backgroundColor": BG_PANEL, "padding": "20px", "border": f"1px solid {BORDER}"})

def cell(text, color=TEXT_PRIMARY):
    return html.Td(text, style={"color": color, "padding": "6px 16px", "fontFamily": FONT_MONO, "fontSize": "11px", "borderBottom": f"1px solid {BORDER}"})

# ---------------------------------------------------------------------------
# App Initialization
# ---------------------------------------------------------------------------
app = dash.Dash(__name__, update_title=None)
server = app.server

app.layout = html.Div([
    dcc.Interval(id="tick", interval=120*1000, n_intervals=0),
    # Header
    html.Div([
        html.H1("NETWORK AUDIT / SIGMON", style={"color": TEXT_PRIMARY, "fontFamily": FONT_MONO, "margin": "0", "fontSize": "22px"}),
        html.Div("ISP PERFORMANCE MONITORING", style={"color": ACCENT_AMBER, "fontFamily": FONT_MONO, "fontSize": "10px", "letterSpacing": "0.3em"})
    ], style={"padding": "30px 40px", "borderBottom": f"1px solid {BORDER}", "backgroundColor": BG_PAGE}),

    html.Div(id="dashboard-content", style={"padding": "20px 40px"})
], style={"backgroundColor": BG_PAGE, "minHeight": "100vh"})

@app.callback(
    Output("dashboard-content", "children"),
    [Input("tick", "n_intervals"),
     Input("mtr-target-selector", "value")],
    prevent_initial_call=False
)
def update_dashboard(n, mtr_target):
    # Set default target if none selected
    mtr_target = mtr_target or "NAPAfrica-JHB"
    
    # Load Data
    df_ookla = load_csv("ookla.csv")
    df_ping  = load_csv("ping.csv")
    df_mtr   = load_csv("mtr.csv")
    # (Other CSVs like iperf3, curl, etc would be loaded here as well)

    # ── MTR Panel Logic ──────────────────────────────────────────────────
    mtr_table_body = [html.Tr(cell("No MTR data found for this target", TEXT_MUTED))]
    
    if df_mtr is not None and "label" in df_mtr.columns:
        df_t = df_mtr[df_mtr["label"] == mtr_target]
        if not df_t.empty:
            latest_ts = df_t["timestamp"].max()
            current_hops = df_t[df_t["timestamp"] == latest_ts].sort_values("hop")
            
            mtr_table_body = []
            for _, row in current_hops.iterrows():
                lat_color = ACCENT_RED if row['avg_ms'] > 150 else (ACCENT_AMBER if row['avg_ms'] > 50 else TEXT_PRIMARY)
                loss_color = ACCENT_RED if row['loss_pct'] > 0 else TEXT_DIM
                
                mtr_table_body.append(html.Tr([
                    cell(f"#{row['hop']}", TEXT_MUTED),
                    cell(row['host'], TEXT_PRIMARY),
                    cell(fmt(row['avg_ms']), lat_color),
                    cell(f"{fmt(row['loss_pct'], 1)}%", loss_color),
                    cell(fmt(row['jitter_ms']), TEXT_MUTED),
                ]))

    mtr_panel = chart_panel([
        html.Div([
            section_header("MTR ROUTING AUDIT", f"Last updated: {datetime.now().strftime('%H:%M:%S')}"),
            dcc.Dropdown(
                id="mtr-target-selector",
                options=[{"label": name, "value": name} for addr, name in MTR_TARGETS],
                value=mtr_target,
                clearable=False,
                style={
                    "width": "250px", "backgroundColor": BG_PANEL, "color": TEXT_PRIMARY,
                    "fontFamily": FONT_MONO, "fontSize": "11px"
                }
            )
        ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "marginBottom": "20px"}),
        
        html.Table([
            html.Thead(html.Tr([
                html.Th(h, style={"fontFamily": FONT_MONO, "fontSize": "9px", "color": TEXT_MUTED, "textAlign": "left", "padding": "4px 16px"}) 
                for h in ["HOP", "NODE HOSTNAME", "AVG (ms)", "LOSS", "JITTER"]
            ])),
            html.Tbody(mtr_table_body)
        ], style={"width": "100%", "borderCollapse": "collapse"})
    ])

    # Construct Layout
    return html.Div([
        # (KPI strip would go here)
        mtr_panel,
        html.Div(style={"height": "20px"}),
        # (Other panels like ookla_panel, ping_panel would follow)
    ])

if __name__ == "__main__":
    app.run_server(host="0.0.0.0", port=8050, debug=False)