import math
import argparse
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import dash
from dash import dcc, html, ctx
from dash.dependencies import Input, Output, State
import webbrowser
import os
import threading
import time
import re

def format_time(sec):
    if pd.isna(sec): return ""
    m, s = divmod(int(sec), 60)
    return f"{m:02d}:{s:02d}"

def parse_eval(val):
    if isinstance(val, str):
        if '#' in val:
            num = int(val.replace('#', ''))
            return 20.0 if num > 0 else -20.0
        try:
            return float(val)
        except:
            return 0.0
    return float(val)

def safe_fmt(val, fmt=""):
    """Safely formats numerical values for the tooltip, handling NaNs seamlessly."""
    if pd.isna(val): return "N/A"
    try:
        if fmt:
            return f"{float(val):{fmt}}"
        return str(val)
    except:
        return str(val)

# --- GRAPH GENERATION ENGINE ---
def create_figure(csv_path, selected_metrics=None, line_style='spline', is_static=False):
    if selected_metrics is None or len(selected_metrics) == 0:
        selected_metrics = ['KSI']

    if is_static:
        selected_metrics = ['KSI', 'Fragility', 'Desperation', 'Forgiveness', 'Intuitiveness', 'Time_Pressure', 'Awareness_WP']

    generic_title = "Kirsch Stress Index (KSI)"
    generic_fig = go.Figure().update_layout(template="plotly_dark", title="Waiting for game data...")

    try:
        df = pd.read_csv(csv_path)
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return generic_fig, generic_title

    if df.empty:
        return generic_fig, generic_title

    # 1. DYNAMIC TITLE EXTRACTION
    game_title = generic_title
    try:
        w_name = df[df['Color'] == 'White']['Player_Name'].iloc[0] if not df[df['Color'] == 'White'].empty else "White"
        b_name = df[df['Color'] == 'Black']['Player_Name'].iloc[0] if not df[df['Color'] == 'Black'].empty else "Black"
        date_str = df['Date'].iloc[0] if 'Date' in df.columns else "????.??.??"
        game_title = f"{w_name} (White) vs. {b_name} (Black) - {date_str}"
    except Exception:
        pass

    # 2. CLEANUP & PREP
    df = df.drop_duplicates(subset=['Ply'], keep='last').copy()
    
    for col in ['Best_SF_Move', 'Best_Maia_Move', 'Top_Chaos_Move']:
        if col in df.columns:
            df[col] = df[col].fillna("None")

    # 3. X-AXIS: FRACTIONAL MOVES (1.0 = White, 1.5 = Black)
    df['Fractional_Move'] = df['Move_Number'] + (df['Color'] == 'Black') * 0.5
    
    # 4. Y-AXIS: PARSE, CAP, AND SCALE EVAL (Lichess Arctan Curve)
    df['Raw_Eval'] = df['Eval'].apply(parse_eval)
    df['Plot_Eval'] = df['Raw_Eval'].clip(lower=-20, upper=20)
    
    # Scale factor of 3.0 perfectly stretches the critical -3 to +3 range
    SCALE_FACTOR = 3.0
    df['Scaled_Eval'] = df['Plot_Eval'].apply(lambda x: math.atan(x / SCALE_FACTOR))

    # 5. CREATE MASTER TIMELINE & FORWARD FILL
    max_frac = df['Fractional_Move'].max()
    all_fracs = [i/2 for i in range(2, int(max_frac * 2) + 1)]
    master = pd.DataFrame({'Fractional_Move': all_fracs})

    df_w = df[df['Color'] == 'White'].copy().add_prefix('W_').rename(columns={'W_Fractional_Move': 'Fractional_Move'})
    df_b = df[df['Color'] == 'Black'].copy().add_prefix('B_').rename(columns={'B_Fractional_Move': 'Fractional_Move'})

    master = master.merge(df_w, on='Fractional_Move', how='left')
    master = master.merge(df_b, on='Fractional_Move', how='left')
    master = master.ffill()

    if 'W_Clock_Seconds' in master.columns:
        master['W_Clock_Str'] = master['W_Clock_Seconds'].apply(format_time)
    else:
        master['W_Clock_Str'] = "N/A"

    if 'B_Clock_Seconds' in master.columns:
        master['B_Clock_Str'] = master['B_Clock_Seconds'].apply(format_time)
    else:
        master['B_Clock_Str'] = "N/A"

    # 6. BUILD THE MASTER TOOLTIP HTML
    tooltip_htmls = []
    for _, row in master.iterrows():
        frac = row['Fractional_Move']
        move_num = int(frac)
        is_white_turn = (frac % 1 == 0)
        
        w_move = row.get('W_Move_Played', '...')
        b_move = row.get('B_Move_Played', '...')
        if pd.isna(w_move): w_move = "..."
        if pd.isna(b_move): b_move = "..."
        
        if is_white_turn:
            if w_move == "Thinking...":
                header = f"<span style='font-size: 16px; color: #FFFFFF;'><b>Move {move_num}. {w_name} (White) to play [Thinking...]</b></span>"
            else:
                header = f"<span style='font-size: 16px; color: #FFFFFF;'><b>Move {move_num}. {w_name} (White) to play — Played: {w_move}</b></span>"
        else:
            if b_move == "Thinking...":
                header = f"<span style='font-size: 16px; color: #FFFFFF;'><b>Move {move_num}... {b_name} (Black) to play [Thinking...]</b></span>"
            else:
                header = f"<span style='font-size: 16px; color: #FFFFFF;'><b>Move {move_num}... {b_name} (Black) to play — Played: {b_move}</b></span>"
    
        w_stats = (
            f"<span style='color: #FFFFFF;'><b>{w_name} (White)</b></span><br>"
            f"KSI: <b>{safe_fmt(row.get('W_KSI'), '.1f')}</b> | Eval: {safe_fmt(row.get('W_Eval'))} (True WP: {safe_fmt(row.get('W_Win_Prob'), '.1f')}% | Felt WP: {safe_fmt(row.get('W_Awareness_WP'), '.1f')}%) | Clock: {row.get('W_Clock_Str', 'N/A')}<br>"
            f"Best: {row.get('W_Best_SF_Move', 'N/A')} | Maia: {row.get('W_Best_Maia_Move', 'N/A')} | Chaos: {row.get('W_Top_Chaos_Move', 'N/A')}<br>"
            f"<span style='color: #AAAAAA; font-size: 12px;'><i>Frag: {safe_fmt(row.get('W_Fragility'), '.0f')} | Forg: {safe_fmt(row.get('W_Forgiveness'), '.0f')} | Int: {safe_fmt(row.get('W_Intuitiveness'), '.0f')} | Dsp: {safe_fmt(row.get('W_Desperation'), '.0f')} | TP: {safe_fmt(row.get('W_Time_Pressure'), '.0f')}</i></span>"
        )
        
        b_stats = (
            f"<span style='color: #CCCCCC;'><b>{b_name} (Black)</b></span><br>"
            f"KSI: <b>{safe_fmt(row.get('B_KSI'), '.1f')}</b> | Eval: {safe_fmt(row.get('B_Eval'))} (True WP: {safe_fmt(row.get('B_Win_Prob'), '.1f')}% | Felt WP: {safe_fmt(row.get('B_Awareness_WP'), '.1f')}%) | Clock: {row.get('B_Clock_Str', 'N/A')}<br>"
            f"Best: {row.get('B_Best_SF_Move', 'N/A')} | Maia: {row.get('B_Best_Maia_Move', 'N/A')} | Chaos: {row.get('B_Top_Chaos_Move', 'N/A')}<br>"
            f"<span style='color: #AAAAAA; font-size: 12px;'><i>Frag: {safe_fmt(row.get('B_Fragility'), '.0f')} | Forg: {safe_fmt(row.get('B_Forgiveness'), '.0f')} | Int: {safe_fmt(row.get('B_Intuitiveness'), '.0f')} | Dsp: {safe_fmt(row.get('B_Desperation'), '.0f')} | TP: {safe_fmt(row.get('B_Time_Pressure'), '.0f')}</i></span>"
        )
        
        tooltip = f"{header}<br><br>{w_stats}<br><br>{b_stats}<extra></extra>"
        tooltip_htmls.append(tooltip)
        
    master['Tooltip'] = tooltip_htmls

    # 7. BUILD THE SUBPLOTS
    fig = make_subplots(
        rows=2, cols=1, 
        shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=[0.25, 0.75],
        subplot_titles=("Objective Truth (Centipawns)", "Kirsch Stress Index & Sub-Metrics")
    )

    # --- TOP CHART: CENTIPAWNS ---
    fig.add_trace(
        go.Scatter(
            x=df['Fractional_Move'], y=df['Scaled_Eval'], # <-- NEW: Use the curved data
            mode='lines',
            name='Stockfish Eval',
            line=dict(color='#ffffff', width=2, shape=line_style),
            fill='tozeroy',
            fillcolor='rgba(255, 255, 255, 0.1)',
            hoverinfo='skip'
        ),
        row=1, col=1
    )
    fig.add_hline(y=0, line_dash="dot", line_color="rgba(255,255,255,0.3)", row=1, col=1)

    # --- BOTTOM CHART: DYNAMIC METRICS ---
    dash_styles = {
        'KSI': 'solid', 'Fragility': 'dot', 'Desperation': 'dash', 
        'Forgiveness': 'dashdot', 'Intuitiveness': 'longdash', 
        'Time_Pressure': 'longdashdot', 'Awareness_WP': 'solid'
    }

    COLOR_WHITE_PLAYER = '#FFFFFF'
    COLOR_BLACK_PLAYER = '#000000'

    for metric in selected_metrics:
        style = dash_styles.get(metric, 'solid')
        w_col = f"W_{metric}"
        b_col = f"B_{metric}"
        
        is_visible = True if not is_static or metric == 'KSI' else 'legendonly'
        metric_display_name = metric.replace('_', ' ')

        # WHITE TRACE
        if w_col in master.columns and not master[w_col].isna().all():
            fig.add_trace(go.Scatter(
                x=master['Fractional_Move'], y=master[w_col],
                mode='lines', name=f'W {metric_display_name}',
                line=dict(color=COLOR_WHITE_PLAYER, width=4 if metric == 'KSI' else 2, dash=style, shape=line_style),
                hoverinfo='skip',
                visible=is_visible
            ), row=2, col=1)

        # BLACK TRACE
        if b_col in master.columns and not master[b_col].isna().all():
            fig.add_trace(go.Scatter(
                x=master['Fractional_Move'], y=master[b_col],
                mode='lines', name=f'B {metric_display_name}',
                line=dict(color=COLOR_BLACK_PLAYER, width=4 if metric == 'KSI' else 2, dash=style, shape=line_style),
                hoverinfo='skip',
                visible=is_visible
            ), row=2, col=1)

    # --- INVISIBLE DUMMY TRACE FOR MASTER TOOLTIP ---
    fig.add_trace(go.Scatter(
        x=master['Fractional_Move'],
        y=[50] * len(master),
        mode='lines',
        line=dict(color='rgba(0,0,0,0)', width=0),
        customdata=master[['Tooltip']],
        hovertemplate="%{customdata[0]}",
        showlegend=False,
        hoverinfo='text'
    ), row=2, col=1)

    # --- FORMATTING & ZONES ---
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#111111",
        plot_bgcolor="#2A2A2A",
        margin=dict(l=40, r=40, t=60, b=40),
        hovermode="x unified",
        legend=dict(orientation="v", yanchor="top", y=1.0, xanchor="left", x=1.02),
        hoverlabel=dict(
            bgcolor="#222222",
            font_size=13,
            font_family="sans-serif",
            bordercolor="#444444"
        )
    )

    fig.update_xaxes(hoverformat=" ", gridcolor="#444444", row=1, col=1)
    fig.update_xaxes(title_text="Move Number", dtick=1, hoverformat=" ", gridcolor="#444444", row=2, col=1)

    # Calculate exactly where the ticks should go on the new curve
    tick_cp_values = [-20, -10, -5, -3, -1, 0, 1, 3, 5, 10, 20]
    tick_vals_scaled = [math.atan(v / SCALE_FACTOR) for v in tick_cp_values]
    tick_text = ["-M", "-10", "-5", "-3", "-1", "0", "+1", "+3", "+5", "+10", "+M"]

    fig.update_yaxes(
        title_text="Eval (CP)", 
        tickmode='array',
        tickvals=tick_vals_scaled,
        ticktext=tick_text,
        range=[math.atan(-21 / SCALE_FACTOR), math.atan(21 / SCALE_FACTOR)], 
        gridcolor="#444444", 
        row=1, col=1
    )
    fig.update_yaxes(title_text="Metric Value", range=[0, 100], gridcolor="#444444", row=2, col=1)

    zones = [
        (0, 40, 'rgba(0, 150, 255, 0.05)'),   # Calm
        (40, 65, 'rgba(255, 255, 0, 0.05)'),  # Tension
        (65, 85, 'rgba(255, 128, 0, 0.05)'),  # Pressure
        (85, 100, 'rgba(255, 0, 0, 0.05)')    # Breaking Point
    ]
    for y0, y1, color in zones:
        fig.add_hrect(y0=y0, y1=y1, fillcolor=color, opacity=1, layer="below", line_width=0, row=2, col=1)

    return fig, game_title

# --- LOG PARSER ENGINE ---
# --- LOG PARSER ENGINE ---
def parse_log_file(log_path):
    """Reads the CLI text log and maps each output block to a fractional move."""
    log_dict = {}
    last_block = "Waiting for engine feed..."
    
    if not os.path.exists(log_path):
        return log_dict, last_block

    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        blocks = content.split("========================================================")
        
        current_header = ""
        for block in blocks:
            if not block.strip(): continue
            
            if "⏳" in block:
                current_header = "========================================================\n" + block.strip() + "\n========================================================\n"
                match = re.search(r'\[(\d+)(\.{1,3})\]', block)
                if match:
                    move_num = float(match.group(1))
                    dots = match.group(2)
                    frac = move_num if dots == '.' else move_num + 0.5
                    log_dict[frac] = current_header
                    last_frac = frac
                    last_block = current_header # <--- NEW: Forces the inspector to instantly show the new turn header
            else:
                if current_header and 'last_frac' in locals():
                    log_dict[last_frac] += block.strip() + "\n\n"
                    last_block = log_dict[last_frac]
                    
    except Exception as e:
        last_block = f"Error reading log: {e}"
        
    return log_dict, last_block

# --- LIVE MODE (DASH APP) ---
def run_live(csv_path, log_path, poll_interval_ms):
    app = dash.Dash(__name__, title="KSI Live Dashboard")
    available_metrics = ['KSI', 'Fragility', 'Desperation', 'Forgiveness', 'Intuitiveness', 'Time_Pressure', 'Awareness_WP']

    app.layout = html.Div(style={'backgroundColor': '#111111', 'minHeight': '100vh', 'padding': '20px'}, children=[
        html.H1(id='header-title', children="Kirsch Stress Index (KSI)", style={'color': 'white', 'fontFamily': 'sans-serif', 'marginTop': '0'}),
        
        # CONTROLS
        html.Div(style={'display': 'flex', 'gap': '20px', 'marginBottom': '20px'}, children=[
            html.Div(style={'flex': '1'}, children=[
                html.Label("Select Metrics to Overlay:", style={'color': 'white', 'fontFamily': 'sans-serif'}),
                dcc.Dropdown(
                    id='metric-dropdown',
                    options=[{'label': m.replace('_', ' '), 'value': m} for m in available_metrics],
                    value=['KSI'],
                    multi=True,
                    style={'color': 'black'}
                )
            ]),
            html.Div(children=[
                html.Label("Line Style:", style={'color': 'white', 'fontFamily': 'sans-serif'}),
                dcc.RadioItems(
                    id='line-style-toggle',
                    options=[
                        {'label': ' Smooth (Spline)', 'value': 'spline'},
                        {'label': ' Step (Exact)', 'value': 'hv'}
                    ],
                    value='spline',
                    labelStyle={'color': 'white', 'cursor': 'pointer', 'marginRight': '15px'},
                    style={'display': 'flex', 'marginTop': '10px'}
                )
            ])
        ]),

        # THE GRAPH
        dcc.Graph(id='live-graph', style={'height': '75vh'}),
        
        # STATE STORE FOR SMART LOG INSPECTOR
        dcc.Store(id='inspect-mode', data=None),
        
        # THE SMART LOG TERMINAL
        html.Div(style={'marginTop': '20px', 'backgroundColor': '#000000', 'border': '1px solid #444', 'borderRadius': '5px', 'padding': '15px'}, children=[
            html.Div(style={'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center', 'marginBottom': '10px'}, children=[
                html.H3(id='log-header', children="Live Engine Feed", style={'color': '#888', 'margin': '0', 'fontFamily': 'sans-serif'}),
                html.Button("🔄 Return to Live Edge", id='btn-live', style={
                    'backgroundColor': '#444', 'color': 'white', 'border': 'none', 'padding': '8px 15px', 'borderRadius': '4px', 'cursor': 'pointer', 'fontWeight': 'bold'
                })
            ]),
            html.Pre(id='live-log-output', style={
                'color': '#00FF00', 
                'fontFamily': 'monospace', 
                'fontSize': '14px',
                'minHeight': '500px',  # <-- NEW: Gives it a solid baseline height
                'height': 'auto',      # <-- NEW: Tells it to expand to fit all the text
                'whiteSpace': 'pre-wrap',
                'margin': '0'
                # Removed overflowY entirely so it never generates an inner scrollbar
            })
        ]),

        dcc.Interval(id='interval-component', interval=poll_interval_ms, n_intervals=0)
    ])

    @app.callback(
        [Output('live-graph', 'figure'),
         Output('header-title', 'children'),
         Output('live-log-output', 'children'),
         Output('log-header', 'children'),
         Output('log-header', 'style'),
         Output('inspect-mode', 'data')],
        [Input('interval-component', 'n_intervals'),
         Input('metric-dropdown', 'value'),
         Input('line-style-toggle', 'value'),
         Input('live-graph', 'clickData'),
         Input('btn-live', 'n_clicks')],
        [State('inspect-mode', 'data')]
    )
    def update_dashboard(n, selected_metrics, line_style, clickData, btn_live, current_inspect_mode):
        # 1. GENERATE THE GRAPH
        if not selected_metrics:
            selected_metrics = ['KSI']
        fig, title = create_figure(csv_path, selected_metrics, line_style, is_static=False)
        
        # 2. DETERMINE INSPECTION STATE
        triggered_id = ctx.triggered_id
        
        if triggered_id == 'btn-live':
            current_inspect_mode = None  # Reset to live
        elif triggered_id == 'live-graph' and clickData:
            try:
                # Extract the X-axis value (Fractional Move) that the user clicked
                clicked_x = clickData['points'][0]['x']
                current_inspect_mode = clicked_x
            except:
                pass

        # 3. PARSE THE LOG FILE
        log_dict, live_block = parse_log_file(log_path)
        
        # 4. EXTRACT LIVE STATUS & ROUTE DATA
        live_status_str = "Auto-Updating"
        try:
            # Peek at the CSV to see exactly who is on the clock
            df_live = pd.read_csv(csv_path)
            if not df_live.empty:
                last_row = df_live.iloc[-1]
                live_move = int(last_row['Move_Number'])
                live_color = last_row['Color']
                live_player = last_row['Player_Name']
                live_action = last_row['Move_Played']
                
                dots = "." if live_color == "White" else "..."
                if live_action == "Thinking...":
                    live_status_str = f"Move {live_move}{dots} {live_player} ({live_color}) is Thinking..."
                else:
                    live_status_str = f"Move {live_move}{dots} {live_player} ({live_color}) played {live_action}"
        except:
            pass

        if current_inspect_mode is None:
            # LIVE MODE
            log_text = live_block
            log_title = f"🟢 LIVE EDGE: {live_status_str}"
            log_title_style = {'color': '#00FF00', 'margin': '0', 'fontFamily': 'sans-serif'} # Green text
        else:
            # INSPECT MODE
            move_num = int(current_inspect_mode)
            color_str = "White" if current_inspect_mode % 1 == 0 else "Black"
            
            log_title = f"⏸️ Inspection Mode: Move {move_num} ({color_str})"
            log_title_style = {'color': '#FF8000', 'margin': '0', 'fontFamily': 'sans-serif'} # Orange text
            
            if current_inspect_mode in log_dict:
                log_text = log_dict[current_inspect_mode]
            else:
                log_text = f"No CLI log data found for Move {move_num} ({color_str}).\n\n(This usually happens if the move was fast-forwarded or played before the script started)."

        return fig, title, log_text, log_title, log_title_style, current_inspect_mode

    def open_browser():
        time.sleep(1.5)
        webbrowser.open("http://127.0.0.1:8050/")
        
    threading.Thread(target=open_browser, daemon=True).start()
    
    print("\n[*] Starting Live KSI Dashboard with Smart Log Inspector...")
    print("[*] Dashboard running at: http://127.0.0.1:8050/")
    print("[*] Press Ctrl+C to quit.\n")
    
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    
    app.run(debug=False, port=8050)

# --- FULL MODE (STATIC HTML) ---
def run_full(csv_path, output_html):
    print(f"[*] Generating full game graph from {csv_path}...")
    fig, title = create_figure(csv_path, is_static=True)
    
    graph_div = fig.to_html(full_html=False, include_plotlyjs='cdn', default_height='85vh')
    
    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>KSI Static Dashboard</title>
        <style>
            body {{
                background-color: #111111;
                margin: 0;
                padding: 20px;
                font-family: sans-serif;
                color: white;
            }}
            h1 {{
                font-family: sans-serif;
                margin-top: 0;
                margin-bottom: 20px;
            }}
        </style>
    </head>
    <body>
        <h1>{title}</h1>
        {graph_div}
    </body>
    </html>
    """
    
    with open(output_html, "w", encoding="utf-8") as f:
        f.write(html_template)
        
    print(f"[*] Graph saved to {output_html}")
    webbrowser.open('file://' + os.path.realpath(output_html))

# --- CLI ENTRY POINT ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="KSI Visualizer - Live Dashboard and Graphing Tool")
    parser.add_argument("--mode", choices=["live", "full"], default="live", help="Run mode: 'live' dashboard or 'full' static HTML export.")
    parser.add_argument("--csv", default="chess.csv", help="Path to the KSI telemetry CSV file.")
    parser.add_argument("--log", default="ksi_log.txt", help="Path to the CLI output text file (for live dashboard).")
    parser.add_argument("--out", default="chess.html", help="Output filename for full mode HTML.")
    parser.add_argument("--poll", type=int, default=3, help="Polling interval for live mode in seconds.")
    
    args = parser.parse_args()

    if args.mode == "live":
        run_live(args.csv, args.log, args.poll * 1000)
    else:
        run_full(args.csv, args.out)