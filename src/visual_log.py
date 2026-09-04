import base64
import io
import json
import copy

import dash
from dash import dcc, html, Input, Output, State, ALL, callback_context
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.FLATLY, dbc.icons.BOOTSTRAP],
    suppress_callback_exceptions=True,
    title="Battery Log Analyzer",
)

# ---------------------------------------------------------------------------
# Chart color palette
# ---------------------------------------------------------------------------

C = {
    'voltage':      '#5B6BBF',
    'current':      '#2C3E50',
    'power_pos':    '#27AE60',
    'power_neg':    '#E74C3C',
    'soc':          '#2980B9',
    'soh':          '#1ABC9C',
    'cell_max':     '#E74C3C',
    'cell_min':     '#3498DB',
    'cell_corr':    '#9B59B6',
    'temp_max':     '#E74C3C',
    'temp_min':     '#3498DB',
    'temp_amb':     '#27AE60',
    'temp_pcb':     '#F39C12',
    'resistance':   '#795548',
    'cell_ir':      '#FF7043',
    'sop_ch':       '#2ECC71',
    'sop_dch':      '#E74C3C',
    'muted':        '#95A5A6',
}

CHART_LAYOUT = dict(
    template='plotly_white',
    hovermode='x unified',
    xaxis_title='',
    margin=dict(l=10, r=10, t=40, b=30),
    legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
    font=dict(family='Inter, system-ui, sans-serif', size=12),
)

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

app.layout = dbc.Container([
    dcc.Store(id='memory-store'),
    dcc.Download(id='download-html'),

    # ── Header ──────────────────────────────────────────────────────────────
    dbc.Row([
        dbc.Col([
            html.Div([
                html.I(className='bi bi-battery-charging me-3 text-primary', style={'fontSize': '2rem'}),
                html.Div([
                    html.H2('Battery Log Analyzer', className='mb-0 fw-bold'),
                    html.Small('CEGASA BCS · Professional Log Viewer', className='text-muted'),
                ]),
            ], className='d-flex align-items-center py-3'),
        ], md=8),
        dbc.Col([
            html.Div(id='header-badge', className='text-end pt-3'),
        ], md=4),
    ], className='border-bottom mb-3'),

    # ── Upload ───────────────────────────────────────────────────────────────
    dbc.Row([
        dbc.Col([
            dcc.Upload(
                id='upload-data',
                children=html.Div([
                    html.I(className='bi bi-cloud-upload me-2'),
                    'Drag & drop a CSV log file, or ',
                    html.A('browse', className='text-primary fw-semibold', style={'cursor': 'pointer'}),
                ]),
                style={
                    'width': '100%',
                    'padding': '18px',
                    'borderWidth': '2px',
                    'borderStyle': 'dashed',
                    'borderRadius': '8px',
                    'borderColor': '#BDC3C7',
                    'textAlign': 'center',
                    'color': '#7F8C8D',
                    'background': '#FAFBFC',
                    'cursor': 'pointer',
                },
                multiple=False,
            ),
            html.Div(id='output-filename', className='text-muted small mt-1 ms-1'),
        ], width=12),
    ], className='mb-3'),

    # ── Action bar ───────────────────────────────────────────────────────────
    dbc.Row([
        dbc.Col([
            dbc.Button(
                [html.I(className='bi bi-file-earmark-arrow-down me-2'), 'Export HTML Report'],
                id='btn-download-html',
                color='outline-secondary',
                size='sm',
                style={'display': 'none'},
            ),
        ], className='d-flex align-items-center gap-3 flex-wrap'),
        dbc.Col([
            html.Div([
                html.Span(
                    [html.I(className='bi bi-battery me-1'), 'Strings in parallel:'],
                    className='text-muted small me-2 align-middle',
                ),
                dbc.RadioItems(
                    id='parallel-count',
                    options=[{'label': str(i), 'value': i} for i in range(1, 7)],
                    value=1,
                    inline=True,
                    input_class_name='btn-check',
                    label_class_name='btn btn-outline-primary btn-sm',
                    label_checked_class_name='active',
                    class_name='btn-group',
                ),
            ], id='parallel-selector', className='d-flex align-items-center', style={'display': 'none !important'}),
        ], className='text-end'),
    ], className='mb-2 align-items-center'),

    html.Hr(className='my-2'),

    # ── Dynamic content ──────────────────────────────────────────────────────
    dbc.Spinner(
        html.Div(id='output-graphs'),
        color='primary',
        spinner_style={'width': '2rem', 'height': '2rem'},
    ),

], fluid=True, className='px-4')


# ---------------------------------------------------------------------------
# Helpers: parse & build metadata
# ---------------------------------------------------------------------------

def parse_contents(contents: str, filename: str):
    _, content_string = contents.split(',', 1)
    decoded = base64.b64decode(content_string)
    try:
        df = pd.read_csv(io.StringIO(decoded.decode('utf-8-sig')))
        if 'Timestamp' not in df.columns:
            return None, "'Timestamp' column not found."
        df['Timestamp'] = pd.to_datetime(df['Timestamp'])
        df.sort_values('Timestamp', inplace=True)
        df['Timestamp'] = df['Timestamp'].astype(str)
        return df.to_dict('records'), None
    except Exception as e:
        return None, str(e)


def _info_item(label: str, value: str, mono: bool = False) -> html.Div:
    val_class = 'fw-semibold font-monospace small' if mono else 'fw-semibold'
    return html.Div([
        html.Span(label, className='text-muted small d-block' , style={'fontSize': '0.72rem', 'letterSpacing': '0.04em', 'textTransform': 'uppercase'}),
        html.Span(str(value) if value else '—', className=val_class),
    ], className='me-4 mb-2')


def _fw_badge(label: str, version: str, serial: str) -> html.Div:
    color = '#2980B9' if label == 'MCS' else '#16A085'
    return html.Div([
        dbc.Badge(label, style={'backgroundColor': color, 'fontSize': '0.7rem'}, className='me-2'),
        html.Span(version or '—', className='fw-semibold me-2'),
        html.Span(serial or '', className='text-muted font-monospace', style={'fontSize': '0.75rem'}),
    ], className='mb-1 d-flex align-items-center')


def build_device_info_panel(row: dict) -> dbc.Card | None:
    # Support both old column names (meta_fw_version) and new (meta_mcs_fw)
    model    = row.get('meta_battery_model', '')
    mcs_fw   = row.get('meta_mcs_fw') or row.get('meta_fw_version', '')
    scs_fw   = row.get('meta_scs_fw', '')
    mcs_ser  = row.get('meta_mcs_serial') or row.get('meta_fw_serial', '')
    scs_ser  = row.get('meta_scs_serial', '')
    strings  = row.get('meta_strings', '')
    modules  = row.get('meta_modules_per_string', '')
    capacity = row.get('meta_capacity_ah', '')
    inverter = row.get('meta_inverter', '')

    if not any([model, mcs_fw, mcs_ser]):
        return None

    return dbc.Card([
        dbc.CardBody([
            dbc.Row([

                # ── Identity ─────────────────────────────────────────────
                dbc.Col([
                    html.Div([
                        html.I(className='bi bi-battery-full me-2',
                               style={'fontSize': '1.6rem', 'color': '#2980B9'}),
                        html.Div([
                            html.H4(model or 'Unknown Model',
                                    className='mb-0 fw-bold',
                                    style={'color': '#2C3E50'}),
                            html.Span('Battery Model', className='text-muted',
                                      style={'fontSize': '0.72rem', 'textTransform': 'uppercase',
                                             'letterSpacing': '0.04em'}),
                        ]),
                    ], className='d-flex align-items-center'),
                ], md=3, className='border-end pe-3'),

                # ── Firmware versions ─────────────────────────────────────
                dbc.Col([
                    html.Div([
                        html.Span('FIRMWARE', className='text-muted d-block mb-2',
                                  style={'fontSize': '0.72rem', 'letterSpacing': '0.06em',
                                         'textTransform': 'uppercase', 'fontWeight': '600'}),
                        _fw_badge('MCS', mcs_fw, mcs_ser),
                        _fw_badge('SCS', scs_fw, scs_ser) if (scs_fw or scs_ser) else html.Div(
                            [dbc.Badge('SCS', style={'backgroundColor': '#16A085', 'fontSize': '0.7rem'}, className='me-2'),
                             html.Span('—', className='text-muted')],
                            className='mb-1 d-flex align-items-center'
                        ),
                    ], className='ps-3'),
                ], md=4, className='border-end'),

                # ── Battery specs ─────────────────────────────────────────
                dbc.Col([
                    html.Div([
                        html.Span('BATTERY SPECS', className='text-muted d-block mb-2',
                                  style={'fontSize': '0.72rem', 'letterSpacing': '0.06em',
                                         'textTransform': 'uppercase', 'fontWeight': '600'}),
                        html.Div([
                            _info_item('Topology',
                                       f'{strings} string × {modules} modules' if strings else '—'),
                            _info_item('Capacity', f'{capacity} Ah' if capacity else '—'),
                            _info_item('Inverter', inverter or '—'),
                        ], className='d-flex flex-wrap'),
                    ], className='ps-3'),
                ], md=5),

            ], align='center'),
        ], className='py-3'),
    ],
    className='mb-3 border-0 shadow-sm',
    style={'borderLeft': '4px solid #2980B9', 'borderRadius': '8px'})


def _stat_card(icon: str, label: str, value: str, color: str = 'primary') -> dbc.Col:
    return dbc.Col([
        dbc.Card([
            dbc.CardBody([
                html.Div([
                    html.I(className=f'bi {icon} me-2', style={'color': color, 'fontSize': '1.1rem'}),
                    html.Span(label, className='text-muted small'),
                ], className='d-flex align-items-center mb-1'),
                html.H5(value, className='mb-0 fw-bold'),
            ], className='py-2 px-3'),
        ], className='border-0 shadow-sm h-100'),
    ], md=2, sm=4, xs=6, className='mb-2')


def build_session_stats(df: pd.DataFrame) -> html.Div:
    row1, row2 = [], []

    # ── Row 1: time & charge stats ───────────────────────────────────────────
    if 'Timestamp' in df.columns:
        ts = pd.to_datetime(df['Timestamp'])
        delta = ts.max() - ts.min()
        total_s = int(delta.total_seconds())
        h, rem = divmod(total_s, 3600)
        m, s = divmod(rem, 60)
        row1.append(_stat_card('bi-clock', 'Duration', f'{h:02d}:{m:02d}:{s:02d}', '#2980B9'))

    row1.append(_stat_card('bi-table', 'Records', f'{len(df):,}', '#27AE60'))

    if 'soc' in df.columns:
        soc_min = df['soc'].min()
        soc_max = df['soc'].max()
        row1.append(_stat_card('bi-battery-half', 'SOC Range', f'{soc_min:.1f}% – {soc_max:.1f}%', '#8E44AD'))

    if 'temperature_tempMax' in df.columns:
        row1.append(_stat_card('bi-thermometer-high', 'Max Temp', f"{df['temperature_tempMax'].max():.1f} °C", '#E74C3C'))

    if 'current' in df.columns:
        peak_ch = df['current'].max()
        peak_dch = df['current'].min()
        if peak_ch > 0:
            row1.append(_stat_card('bi-arrow-up-circle', 'Peak Charge', f'{peak_ch:.1f} A', '#27AE60'))
        if peak_dch < 0:
            row1.append(_stat_card('bi-arrow-down-circle', 'Peak Discharge', f'{abs(peak_dch):.1f} A', '#E74C3C'))

    # ── Row 2: cell & SOC detail stats ──────────────────────────────────────
    if 'vcell_vcellMax' in df.columns:
        row2.append(_stat_card('bi-chevron-double-up', 'Max Cell V', f"{df['vcell_vcellMax'].max()} mV", '#E74C3C'))

    if 'vcell_vcellMin' in df.columns:
        row2.append(_stat_card('bi-chevron-double-down', 'Min Cell V', f"{df['vcell_vcellMin'].min()} mV", '#3498DB'))

    if 'vcell_vcellMax' in df.columns and 'vcell_vcellMin' in df.columns:
        # Worst-case spread across the session
        spread = (df['vcell_vcellMax'] - df['vcell_vcellMin']).max()
        row2.append(_stat_card('bi-arrows-expand', 'Max Cell Spread', f'{spread} mV', '#F39C12'))

    if 'soc' in df.columns:
        # Biggest SOC jump between consecutive rows — flags fast events or anomalies
        soc_jump = df['soc'].diff().abs().max()
        row2.append(_stat_card('bi-lightning', 'Biggest SOC Jump', f'{soc_jump:.2f}%', '#9B59B6'))

    if 'vcell_internalResistance' in df.columns:
        ir_max = df['vcell_internalResistance'].max()
        row2.append(_stat_card('bi-activity', 'Max Pack IR', f'{ir_max:.1f} mΩ', '#795548'))

    if 'temperature_tempMax' in df.columns and 'temperature_tempMin' in df.columns:
        temp_spread = (df['temperature_tempMax'] - df['temperature_tempMin']).max()
        row2.append(_stat_card('bi-thermometer-half', 'Max Temp Spread', f'{temp_spread:.1f} °C', '#E67E22'))

    return html.Div([
        dbc.Row(row1, className='g-2 mb-2'),
        dbc.Row(row2, className='g-2 mb-3'),
    ])


# ---------------------------------------------------------------------------
# Chart builders
# ---------------------------------------------------------------------------

def _fig(title: str, y_label: str) -> go.Figure:
    fig = go.Figure(layout={**CHART_LAYOUT, 'title': {'text': title, 'font': {'size': 14}}})
    fig.update_yaxes(title_text=y_label)
    return fig


def create_figures(df: pd.DataFrame) -> dict:
    if 'Timestamp' in df.columns and pd.api.types.is_string_dtype(df['Timestamp']):
        df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    x = df['Timestamp']

    figs = {}

    # 1. Power
    fig = _fig('Power', 'W')
    if 'power' in df.columns:
        pos = df['power'].clip(lower=0)
        neg = df['power'].clip(upper=0)
        fig.add_trace(go.Scatter(
            x=x, y=pos, name='Charging', fill='tozeroy',
            line=dict(color=C['power_pos'], width=1.5),
            fillcolor='rgba(39,174,96,0.15)',
        ))
        fig.add_trace(go.Scatter(
            x=x, y=neg, name='Discharging', fill='tozeroy',
            line=dict(color=C['power_neg'], width=1.5),
            fillcolor='rgba(231,76,60,0.15)',
        ))
    figs['power'] = fig

    # 2. Voltage
    fig = _fig('Battery Voltage', 'V')
    if 'voltage' in df.columns:
        fig.add_trace(go.Scatter(x=x, y=df['voltage'], name='Voltage',
                                  line=dict(color=C['voltage'], width=2)))
    if 'sop_vCh' in df.columns:
        fig.add_trace(go.Scatter(x=x, y=df['sop_vCh'], name='SOP Vch',
                                  line=dict(color=C['sop_ch'], dash='dot', width=1)))
    if 'sop_vDisch' in df.columns:
        fig.add_trace(go.Scatter(x=x, y=df['sop_vDisch'], name='SOP Vdch',
                                  line=dict(color=C['sop_dch'], dash='dot', width=1)))
    figs['voltage'] = fig

    # 3. Current
    fig = _fig('Current & SOP Limits', 'A')
    if 'current' in df.columns:
        fig.add_trace(go.Scatter(x=x, y=df['current'], name='Current',
                                  line=dict(color=C['current'], width=2)))
    if 'sop_iCh' in df.columns:
        fig.add_trace(go.Scatter(x=x, y=df['sop_iCh'], name='SOP Ich',
                                  line=dict(color=C['sop_ch'], dash='dot', width=1)))
    if 'sop_iDisch' in df.columns:
        fig.add_trace(go.Scatter(x=x, y=-df['sop_iDisch'], name='SOP Idch',
                                  line=dict(color=C['sop_dch'], dash='dot', width=1)))
    figs['current'] = fig

    # 4. SOC & SOH
    fig = _fig('State of Charge & Health', '%')
    if 'soc' in df.columns:
        fig.add_trace(go.Scatter(x=x, y=df['soc'], name='SOC', fill='tozeroy',
                                  line=dict(color=C['soc'], width=2),
                                  fillcolor='rgba(41,128,185,0.1)'))
    if 'soh' in df.columns:
        fig.add_trace(go.Scatter(x=x, y=df['soh'], name='SOH',
                                  line=dict(color=C['soh'], width=2, dash='dash')))
    fig.update_yaxes(range=[0, 100])
    figs['soc'] = fig

    # 5. Cell Voltages
    fig = _fig('Cell Voltages', 'mV')
    if 'vcell_vcellMax' in df.columns:
        fig.add_trace(go.Scatter(x=x, y=df['vcell_vcellMax'], name='Max',
                                  line=dict(color=C['cell_max'], width=1.5)))
    if 'vcell_vcellMin' in df.columns:
        fig.add_trace(go.Scatter(x=x, y=df['vcell_vcellMin'], name='Min',
                                  line=dict(color=C['cell_min'], width=1.5)))
    if 'vcell_vcellAvg' in df.columns:
        fig.add_trace(go.Scatter(x=x, y=df['vcell_vcellAvg'], name='Avg',
                                  line=dict(color=C['muted'], width=1, dash='dot')))
    if 'vcell_corrected_vcell' in df.columns:
        fig.add_trace(go.Scatter(x=x, y=df['vcell_corrected_vcell'], name='Corrected',
                                  line=dict(color=C['cell_corr'], width=2, dash='dash')))
    figs['vcell'] = fig

    # 6. Temperatures
    fig = _fig('Temperatures', '°C')
    if 'temperature_tempMax' in df.columns:
        fig.add_trace(go.Scatter(x=x, y=df['temperature_tempMax'], name='Max',
                                  line=dict(color=C['temp_max'], width=2)))
    if 'temperature_tempMin' in df.columns:
        fig.add_trace(go.Scatter(x=x, y=df['temperature_tempMin'], name='Min',
                                  line=dict(color=C['temp_min'], width=1.5)))
    if 'temperature_tempAmb' in df.columns:
        fig.add_trace(go.Scatter(x=x, y=df['temperature_tempAmb'], name='Ambient',
                                  line=dict(color=C['temp_amb'], dash='dot', width=1.5)))
    if 'temperature_tempPCB' in df.columns:
        fig.add_trace(go.Scatter(x=x, y=df['temperature_tempPCB'], name='PCB',
                                  line=dict(color=C['temp_pcb'], dash='dot', width=1)))
    figs['temp'] = fig

    return figs


# ---------------------------------------------------------------------------
# Cycle analysis
# ---------------------------------------------------------------------------

def detect_cycles(df: pd.DataFrame) -> list[dict]:
    """Extract charge/discharge cycles from BMS capacity counters.

    Boundaries are detected from large drops in capacityDchCurrentCycle /
    capacityChCurrentCycle (the BMS resets each counter when the opposite
    half-cycle begins).  SOC is taken at the first/last row of each segment;
    theoretical Ah is derived from usefulCapacity × ΔSOC.
    """
    required = {
        'capacity_capacityDchCurrentCycle',
        'capacity_capacityChCurrentCycle',
        'soc',
        'Timestamp',
    }
    if not required.issubset(df.columns):
        return []

    df = df.copy()
    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    df = df.sort_values('Timestamp').reset_index(drop=True)
    df = df.dropna(subset=['soc']).reset_index(drop=True)

    dch = df['capacity_capacityDchCurrentCycle']
    ch  = df['capacity_capacityChCurrentCycle']

    dch_resets = df.index[(dch.diff().fillna(0) < -5)].tolist()
    ch_resets  = df.index[(ch.diff().fillna(0)  < -5)].tolist()

    events = (
        [(i, 'dch') for i in dch_resets] +
        [(i, 'ch')  for i in ch_resets]
    )
    events.sort(key=lambda e: e[0])

    bounds = [0] + [e[0] for e in events] + [len(df)]

    def _seg_kind(k: int) -> str:
        if k < len(events):
            return 'discharge' if events[k][1] == 'dch' else 'charge'
        if events:
            return 'charge' if events[-1][1] == 'dch' else 'discharge'
        return 'charge' if ch.max() >= dch.max() else 'discharge'

    useful_cap   = float(df['capacity_usefulCapacity'].iloc[0]) if 'capacity_usefulCapacity' in df.columns else 0.0
    nominal_cap  = float(df['meta_capacity_ah'].iloc[0])        if 'meta_capacity_ah'        in df.columns else 0.0

    cycles = []
    MIN_DELTA_SOC = 50.0  # ignore segments shallower than this (noise, brief balancing pulses)

    for k in range(len(bounds) - 1):
        si, ei = bounds[k], bounds[k + 1] - 1
        seg  = df.iloc[si:ei + 1]
        if len(seg) < 2:
            continue

        if abs(float(seg['soc'].iloc[0]) - float(seg['soc'].iloc[-1])) < MIN_DELTA_SOC:
            continue

        kind = _seg_kind(k)

        # Validate against dominant current direction: overrides if BMS reset counter
        # mid-cycle (e.g. BMS restarts its Ah counter without changing direction)
        if 'current' in df.columns and len(seg) >= 3:
            mean_cur = float(df['current'].iloc[si:ei + 1].mean())
            current_kind = 'charge' if mean_cur > 0 else 'discharge'
            if current_kind != kind:
                kind = current_kind

        ah   = float(dch.iloc[si:ei + 1].max() if kind == 'discharge' else ch.iloc[si:ei + 1].max())

        # Coulombometry: ∫ |I| dt / 3600  (independent of BMS counter)
        if 'current' in df.columns:
            seg_cur = df['current'].iloc[si:ei + 1].values
            seg_ts  = df['Timestamp'].iloc[si:ei + 1]
            dt_s    = seg_ts.diff().dt.total_seconds().fillna(0).values
            ah_calc = float(abs((seg_cur * dt_s).sum()) / 3600.0)
        else:
            ah_calc = None

        soc_start  = float(seg['soc'].iloc[0])
        soc_end    = float(seg['soc'].iloc[-1])
        delta_soc  = abs(soc_start - soc_end)
        t_start    = seg['Timestamp'].iloc[0]
        t_end      = seg['Timestamp'].iloc[-1]
        dur_s      = int((t_end - t_start).total_seconds())
        hh, rem    = divmod(dur_s, 3600)
        mm, ss     = divmod(rem, 60)

        # First segment partial if counter already had a non-zero value at log start
        partial_start = k == 0 and (
            (kind == 'charge'    and float(ch.iloc[si])  > 5) or
            (kind == 'discharge' and float(dch.iloc[si]) > 5)
        )
        partial_end = k == len(events)

        note_parts = []
        if partial_start:
            note_parts.append('Partial (log start)')
        if partial_end:
            note_parts.append('Partial (log end)')

        theo_ah    = useful_cap * delta_soc / 100.0 if useful_cap > 0 else None
        match_pct  = (ah / theo_ah * 100.0)         if (theo_ah and theo_ah > 0 and not partial_start and not partial_end) else None

        cycles.append({
            'n':              k + 1,
            'kind':           kind,
            't_start':        t_start,
            't_end':          t_end,
            'duration':       f'{hh:02d}:{mm:02d}:{ss:02d}',
            'soc_start':      round(soc_start, 1),
            'soc_end':        round(soc_end, 1),
            'delta_soc':      round(delta_soc, 1),
            'ah':             round(ah, 1),
            'ah_calc':        round(ah_calc, 1)   if ah_calc   is not None else None,
            'theo_ah':        round(theo_ah, 1)   if theo_ah   is not None else None,
            'match_pct':      round(match_pct, 1) if match_pct is not None else None,
            'useful_capacity': useful_cap,
            'nominal_capacity': nominal_cap,
            'note':           ' · '.join(note_parts),
        })

    return cycles


def build_cycle_table(cycles: list[dict], n_parallel: int = 1) -> dbc.Card | None:
    if not cycles:
        return None

    n_parallel = max(1, int(n_parallel or 1))
    multi      = n_parallel > 1

    DCH_COLOR  = '#E74C3C'
    CH_COLOR   = '#27AE60'
    DCH_BG     = 'rgba(231,76,60,0.04)'
    CH_BG      = 'rgba(39,174,96,0.04)'
    LABEL_STYLE = {
        'fontSize': '0.72rem', 'letterSpacing': '0.06em',
        'textTransform': 'uppercase', 'fontWeight': '600',
    }

    def _th(label, width, align='left'):
        s = {'width': width, 'color': '#7F8C8D', **LABEL_STYLE}
        if align == 'right':
            s['textAlign'] = 'right'
        return html.Th(label, style=s)

    th_cells = [
        _th('#',          '3%'),
        _th('Type',       '10%'),
        _th('Period',     '20%'),
        _th('Duration',   '8%'),
        _th('SOC Start',  '8%',  'right'),
        _th('SOC End',    '8%',  'right'),
        _th('ΔSOC',       '6%',  'right'),
        _th('Ah Total',   '8%',  'right'),
    ]
    if multi:
        th_cells.append(_th('Ah / String', '8%', 'right'))
    th_cells += [
        _th('Ah (∫I·dt)', '8%',  'right'),
        _th('Theo. Ah',   '8%',  'right'),
        _th('Match',       '6%',  'right'),
        _th('Note',        '6%'),
    ]
    header = html.Thead(html.Tr(th_cells, style={'borderBottom': '2px solid #ECF0F1'}))

    rows = []
    for c in cycles:
        is_dch    = c['kind'] == 'discharge'
        color     = DCH_COLOR if is_dch else CH_COLOR
        bg        = DCH_BG    if is_dch else CH_BG
        icon      = '↓' if is_dch else '↑'
        label     = 'Discharge' if is_dch else 'Charge'
        ah_total  = c['ah']
        ah_string = ah_total / n_parallel

        date_str  = c['t_start'].strftime('%Y-%m-%d')
        period    = f"{date_str}   {c['t_start'].strftime('%H:%M')} → {c['t_end'].strftime('%H:%M')}"

        # Match uses per-string Ah vs per-string theoretical
        match = (ah_string / c['theo_ah'] * 100.0) if (c['theo_ah'] and c['theo_ah'] > 0 and not c['note']) else None
        if match is not None:
            m_color  = '#27AE60' if match >= 95 else ('#F39C12' if match >= 85 else '#E74C3C')
            match_td = html.Td(f'{match:.1f}%', style={'textAlign': 'right', 'color': m_color, 'fontWeight': '600', 'verticalAlign': 'middle'})
        else:
            match_td = html.Td('—', style={'textAlign': 'right', 'color': '#BDC3C7', 'verticalAlign': 'middle'})

        theo_str = f"{c['theo_ah']:.1f}" if c['theo_ah'] is not None else '—'

        td_cells = [
            html.Td(c['n'], style={'color': '#95A5A6', 'verticalAlign': 'middle'}),
            html.Td(
                dbc.Badge([html.Span(icon, style={'marginRight': '4px'}), label],
                          style={'backgroundColor': color, 'fontSize': '0.7rem'}),
                style={'verticalAlign': 'middle'},
            ),
            html.Td(html.Span(period, className='font-monospace', style={'fontSize': '0.8rem'}),
                    style={'verticalAlign': 'middle'}),
            html.Td(html.Span(c['duration'], className='font-monospace'),
                    style={'verticalAlign': 'middle'}),
            html.Td(f"{c['soc_start']:.1f}%", style={'textAlign': 'right', 'verticalAlign': 'middle'}),
            html.Td(f"{c['soc_end']:.1f}%",   style={'textAlign': 'right', 'verticalAlign': 'middle'}),
            html.Td(f"{c['delta_soc']:.1f}%",  style={'textAlign': 'right', 'verticalAlign': 'middle'}),
            html.Td(f"{ah_total:.1f} Ah",
                    style={'textAlign': 'right', 'fontWeight': '600' if not multi else 'normal',
                           'color': '#7F8C8D' if multi else 'inherit', 'verticalAlign': 'middle'}),
        ]
        if multi:
            td_cells.append(
                html.Td(f"{ah_string:.1f} Ah",
                        style={'textAlign': 'right', 'fontWeight': '600', 'verticalAlign': 'middle'})
            )

        # Coulombometry column — divide by n_parallel same as BMS Ah
        ah_calc_str = f"{c['ah_calc'] / n_parallel:.1f} Ah" if c['ah_calc'] is not None else '—'
        td_cells += [
            html.Td(ah_calc_str, style={'textAlign': 'right', 'color': '#8E44AD', 'fontWeight': '600', 'verticalAlign': 'middle'}),
            html.Td(f"{theo_str} Ah", style={'textAlign': 'right', 'color': '#7F8C8D', 'verticalAlign': 'middle'}),
            match_td,
            html.Td(
                html.Span(c['note'], style={'fontSize': '0.72rem', 'color': '#95A5A6'})
                if c['note'] else html.Span('—', style={'color': '#BDC3C7'}),
                style={'verticalAlign': 'middle'},
            ),
        ]
        rows.append(html.Tr(td_cells, style={'backgroundColor': bg}))

    useful_cap  = cycles[0]['useful_capacity']
    nominal_cap = cycles[0]['nominal_capacity']
    complete    = sum(1 for c in cycles if not c['note'])

    caption_parts = [
        'Ah (BMS): BMS internal coulomb counter  ·  Ah (∫I·dt): manual integration of logged current × Δt  ·  Theo. Ah: Useful Capacity × ΔSOC / 100',
        f'Useful Capacity: {useful_cap:.0f} Ah  ·  Match uses Ah/String vs Theo. Ah  ·  only cycles ≥ 50% ΔSOC shown',
    ]
    if nominal_cap:
        caption_parts.append(f'Nominal: {nominal_cap:.0f} Ah')

    return dbc.Card([
        dbc.CardBody([
            html.Div([
                html.I(className='bi bi-arrow-repeat me-2', style={'color': '#2980B9', 'fontSize': '1.1rem'}),
                html.Span('Cycle Analysis', className='fw-semibold', style={'color': '#2C3E50', 'fontSize': '0.95rem'}),
                html.Span(
                    f' · {len(cycles)} segment{"s" if len(cycles) != 1 else ""}'
                    + (f', {complete} complete' if complete < len(cycles) else ''),
                    className='text-muted small ms-1',
                ),
            ], className='mb-3'),
            html.Div(
                dbc.Table(
                    [header, html.Tbody(rows)],
                    bordered=False,
                    hover=True,
                    size='sm',
                    className='mb-0',
                    style={'fontSize': '0.85rem'},
                ),
                style={'overflowX': 'auto'},
            ),
            html.Div(
                [html.Div(line) for line in caption_parts],
                className='text-muted mt-2',
                style={'fontSize': '0.72rem', 'lineHeight': '1.6'},
            ),
        ], className='py-3 px-3'),
    ],
    className='mb-3 border-0 shadow-sm',
    style={'borderLeft': '4px solid #2980B9', 'borderRadius': '8px'})


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

@app.callback(
    [Output('memory-store', 'data'),
     Output('output-filename', 'children'),
     Output('btn-download-html', 'style'),
     Output('header-badge', 'children'),
     Output('parallel-selector', 'style')],
    Input('upload-data', 'contents'),
    State('upload-data', 'filename'),
)
def update_store(contents, filename):
    hidden = {'display': 'none'}
    if contents is None:
        return None, '', {'display': 'none'}, '', hidden

    data, error = parse_contents(contents, filename)
    if error:
        return (
            None,
            dbc.Alert(f'Error: {error}', color='danger', className='py-2 mt-1'),
            {'display': 'none'},
            '',
            hidden,
        )

    df = pd.DataFrame(data)
    ts = pd.to_datetime(df['Timestamp']) if 'Timestamp' in df.columns else None
    date_str = ''
    if ts is not None:
        date_str = ts.min().strftime('%Y-%m-%d')

    badge = dbc.Badge(
        [html.I(className='bi bi-check-circle me-1'), filename],
        color='success', pill=True, className='px-3 py-2',
    )
    filename_hint = html.Span([
        html.I(className='bi bi-file-earmark-text me-1'),
        f'{filename}',
        html.Span(f' · {len(df):,} records', className='text-muted ms-1'),
        html.Span(f' · {date_str}', className='text-muted ms-1') if date_str else '',
    ])

    return data, filename_hint, {'display': 'inline-block'}, badge, {'display': 'flex', 'alignItems': 'center'}


@app.callback(
    Output('output-graphs', 'children'),
    Input('memory-store', 'data'),
    Input('parallel-count', 'value'),
)
def update_graphs(data, n_parallel):
    if data is None:
        return html.Div([
            html.Div([
                html.I(className='bi bi-bar-chart-line text-muted', style={'fontSize': '3rem'}),
                html.P('Upload a CSV log file to begin analysis.', className='text-muted mt-2'),
            ], className='text-center py-5'),
        ])

    df = pd.DataFrame(data)
    figs = create_figures(df)

    # Device info panel (only shown if meta columns present)
    first_row = df.iloc[0].to_dict() if len(df) > 0 else {}
    device_panel = build_device_info_panel(first_row)

    # Session stats
    session_stats = build_session_stats(df)

    # Cycle analysis table
    cycle_table = build_cycle_table(detect_cycles(df), n_parallel=n_parallel or 1)

    def graph(key, **kwargs):
        return dcc.Graph(
            id={'type': 'dynamic-graph', 'index': key},
            figure=figs[key],
            config={'displayModeBar': True, 'modeBarButtonsToRemove': ['lasso2d', 'select2d']},
            **kwargs,
        )

    return html.Div([
        device_panel or html.Div(),
        session_stats,
        cycle_table or html.Div(),
        html.Hr(className='my-3'),

        # Power | Voltage
        dbc.Row([
            dbc.Col(graph('power'), md=6),
            dbc.Col(graph('voltage'), md=6),
        ], className='mb-3'),

        # SOC | Current
        dbc.Row([
            dbc.Col(graph('soc'), md=6),
            dbc.Col(graph('current'), md=6),
        ], className='mb-3'),

        # Cell Voltages | Temperatures
        dbc.Row([
            dbc.Col(graph('vcell'), md=6),
            dbc.Col(graph('temp'), md=6),
        ], className='mb-3'),

    ])


# ---------------------------------------------------------------------------
# Synchronized zoom across all charts
# ---------------------------------------------------------------------------

@app.callback(
    Output({'type': 'dynamic-graph', 'index': ALL}, 'figure'),
    Input({'type': 'dynamic-graph', 'index': ALL}, 'relayoutData'),
    State({'type': 'dynamic-graph', 'index': ALL}, 'figure'),
)
def sync_zoom(relayout_data_list, figures):
    ctx = callback_context
    if not figures or not ctx.triggered:
        return [dash.no_update] * len(figures)

    trigger_value = ctx.triggered[0].get('value')
    if not trigger_value or 'autosize' in trigger_value:
        return [dash.no_update] * len(figures)

    xaxis_range = None
    autorange = False

    if 'xaxis.range[0]' in trigger_value:
        xaxis_range = [trigger_value['xaxis.range[0]'], trigger_value['xaxis.range[1]']]
    elif 'xaxis.range' in trigger_value:
        xaxis_range = trigger_value['xaxis.range']
    elif trigger_value.get('xaxis.autorange'):
        autorange = True

    if not xaxis_range and not autorange:
        return [dash.no_update] * len(figures)

    updated = []
    for fig in figures:
        new_fig = copy.deepcopy(fig)
        xaxis = new_fig.setdefault('layout', {}).setdefault('xaxis', {})
        if xaxis_range:
            xaxis['range'] = xaxis_range
            xaxis['autorange'] = False
        else:
            xaxis['autorange'] = True
            xaxis.pop('range', None)
        updated.append(new_fig)

    return updated


# ---------------------------------------------------------------------------
# HTML report export
# ---------------------------------------------------------------------------

@app.callback(
    Output('download-html', 'data'),
    Input('btn-download-html', 'n_clicks'),
    State('memory-store', 'data'),
    prevent_initial_call=True,
)
def download_html_report(n_clicks, data):
    if not data:
        return dash.no_update

    df = pd.DataFrame(data)
    first_row = df.iloc[0].to_dict() if len(df) > 0 else {}
    figs = create_figures(df)

    model = first_row.get('meta_battery_model', 'Battery')
    serial = first_row.get('meta_fw_serial', '')
    fw = first_row.get('meta_fw_version', '')
    ts = pd.to_datetime(df['Timestamp']) if 'Timestamp' in df.columns else None
    date_range = ''
    if ts is not None:
        date_range = f"{ts.min().strftime('%Y-%m-%d %H:%M')} → {ts.max().strftime('%Y-%m-%d %H:%M')}"

    charts_html = ''.join(
        pio.to_html(fig, full_html=False, include_plotlyjs='cdn')
        for fig in figs.values()
    )

    meta_rows = ''
    for label, val in [
        ('Model', model), ('Serial', serial), ('Firmware', fw),
        ('Records', f"{len(df):,}"), ('Period', date_range),
    ]:
        if val:
            meta_rows += f'<tr><td style="color:#7F8C8D;padding:4px 12px 4px 0">{label}</td><td style="font-weight:600">{val}</td></tr>'

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Battery Log Report — {model}</title>
  <style>
    body {{ font-family: Inter, system-ui, sans-serif; margin: 0; padding: 24px; background: #f8f9fa; color: #2C3E50; }}
    .header {{ background: #fff; border-radius: 8px; padding: 24px 32px; margin-bottom: 24px; box-shadow: 0 1px 4px rgba(0,0,0,.08); display: flex; justify-content: space-between; align-items: flex-start; }}
    .header h1 {{ margin: 0 0 4px; font-size: 1.6rem; color: #2980B9; }}
    .header small {{ color: #7F8C8D; }}
    .meta-table {{ border-collapse: collapse; font-size: 0.9rem; }}
    .chart-wrap {{ background: #fff; border-radius: 8px; margin-bottom: 20px; padding: 8px; box-shadow: 0 1px 4px rgba(0,0,0,.06); }}
    .footer {{ text-align: center; color: #BDC3C7; font-size: 0.8rem; margin-top: 32px; }}
  </style>
</head>
<body>
  <div class="header">
    <div>
      <h1>&#128267; {model}</h1>
      <small>Battery Log Analysis Report</small>
    </div>
    <table class="meta-table">{meta_rows}</table>
  </div>
  {''.join(f'<div class="chart-wrap">{c}</div>' for c in [
      pio.to_html(fig, full_html=False, include_plotlyjs='cdn') for fig in figs.values()
  ])}
  <div class="footer">Generated {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')} · Battery Log Analyzer</div>
</body>
</html>"""

    safe_name = model.replace(' ', '_') or 'battery'
    return dict(content=html_content, filename=f'battery_report_{safe_name}.html')


if __name__ == '__main__':
    app.run(debug=True, port=8050, host='0.0.0.0')
