"""Plotly figure builders — pure presentation, ported verbatim from the old
visual_log.py. No business logic here."""

import pandas as pd
import plotly.graph_objects as go

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

# BMS `status` is a raw int with no string form from the API. We've only ever
# observed status=0 (normal) in real data, so this label mapping is an
# UNVERIFIED BEST GUESS pending confirmation from CEGASA BMS docs — correct
# it here once the real code→severity mapping is known.
STATE_STATUS_LABELS = {1: 'CAUTION', 2: 'WARNING', 3: 'ALARM'}
STATE_COLORS = {
    'READY': '#95A5A6', 'CONNECTING': '#3498DB', 'RUN': C['power_pos'],
    'DISCONNECTING': '#9B59B6', 'CAUTION': '#F1C40F', 'WARNING': '#E67E22',
    'ALARM': C['power_neg'],
}

CHART_LAYOUT = dict(
    template='plotly_white',
    hovermode='x unified',
    xaxis_title='',
    margin=dict(l=10, r=10, t=40, b=30),
    legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
    font=dict(family='Inter, system-ui, sans-serif', size=12),
)


def _fig(title: str, y_label: str) -> go.Figure:
    fig = go.Figure(layout={**CHART_LAYOUT, 'title': {'text': title, 'font': {'size': 14}}})
    fig.update_yaxes(title_text=y_label)
    return fig


def _drop_below(series: pd.Series, floor: float) -> pd.Series:
    """BMS comm glitches don't always land on exactly 0 — sometimes it's a
    partial/garbage read that lands near-but-not-at 0 (e.g. a cell voltage
    truncated to ~1000 mV while its neighbours sit at ~3300 mV). A fixed
    `!= 0` test misses those. Instead mask anything below a floor that's
    physically implausible for this system while connected and logging, so
    a single glitchy sample becomes a gap instead of dragging the y-axis
    autorange down and crushing the real signal.
    """
    return series.where(series >= floor)


def _state_label_series(df: pd.DataFrame, col) -> pd.Series | None:
    """Severity (status != 0) takes precedence over operating state
    (state_str) when both are present for a timestamp — see STATE_STATUS_LABELS."""
    has_state = col('state_str') in df.columns
    has_status = col('status') in df.columns
    if not has_state and not has_status:
        return None

    def label(row):
        status = row.get(col('status')) if has_status else None
        if pd.notna(status) and int(status) != 0:
            return STATE_STATUS_LABELS.get(int(status), f'STATUS_{int(status)}')
        state = row.get(col('state_str')) if has_state else None
        return state if isinstance(state, str) and state else 'UNKNOWN'

    return df.apply(label, axis=1)


def _state_segments(x: pd.Series, labels: pd.Series) -> list[dict]:
    """Run-length encodes consecutive identical state labels into
    contiguous time segments. A per-sample line/marker trace lets a long
    RUN stretch visually swallow brief states on a large log (a single
    transition sample renders as a near-invisible one-pixel spike) — a
    segment always gets real screen width regardless of how briefly the
    BMS was in it.
    """
    if labels.empty:
        return []

    group = (labels != labels.shift()).cumsum()
    starts = x.groupby(group).first()
    ends = x.groupby(group).last()
    seg_labels = labels.groupby(group).first()

    step = x.diff().median()
    if pd.isna(step) or step <= pd.Timedelta(0):
        step = pd.Timedelta(seconds=1)

    # Segments end where the next one starts, so they render as touching
    # blocks; the last segment has no "next" to borrow from, so it gets one
    # synthetic sampling step of width instead of collapsing to zero — it's
    # often the current, most important state on a live log.
    next_starts = starts.shift(-1)
    next_starts.iloc[-1] = ends.iloc[-1] + step

    return [
        {'label': label, 'start': start, 'end': end}
        for label, start, end in zip(seg_labels, starts, next_starts)
    ]


def create_figures(df: pd.DataFrame, prefix: str = '') -> dict:
    """Builds the standard chart set from `df` columns under `prefix`.

    `prefix=''` reads pack-level columns (voltage, soc, vcell_vcellMax, ...).
    `prefix='string1_'` reads that string's columns instead (string1_voltage,
    string1_soc, string1_vcell_vcellMax, ...) — same builders, no duplicated
    chart code between the pack-level and per-string views.
    """
    def col(name: str) -> str:
        return f'{prefix}{name}'

    if 'Timestamp' in df.columns and pd.api.types.is_string_dtype(df['Timestamp']):
        df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    x = df['Timestamp']

    figs = {}

    # 1. Power
    fig = _fig('Power', 'W')
    if col('power') in df.columns:
        pos = df[col('power')].clip(lower=0)
        neg = df[col('power')].clip(upper=0)
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
    # Floor is well below any real pack voltage (15 cells in series never
    # legitimately drops under ~30 V) but comfortably above 0, to catch
    # both a literal 0 and a near-zero garbage read.
    fig = _fig('Battery Voltage', 'V')
    if col('voltage') in df.columns:
        fig.add_trace(go.Scatter(x=x, y=_drop_below(df[col('voltage')], 20), name='Voltage',
                                  line=dict(color=C['voltage'], width=2)))
    if col('sop_vCh') in df.columns:
        fig.add_trace(go.Scatter(x=x, y=_drop_below(df[col('sop_vCh')], 20), name='SOP Vch',
                                  line=dict(color=C['sop_ch'], dash='dot', width=1)))
    if col('sop_vDisch') in df.columns:
        fig.add_trace(go.Scatter(x=x, y=_drop_below(df[col('sop_vDisch')], 20), name='SOP Vdch',
                                  line=dict(color=C['sop_dch'], dash='dot', width=1)))
    figs['voltage'] = fig

    # 3. Current
    fig = _fig('Current & SOP Limits', 'A')
    if col('current') in df.columns:
        fig.add_trace(go.Scatter(x=x, y=df[col('current')], name='Current',
                                  line=dict(color=C['current'], width=2)))
    if col('sop_iCh') in df.columns:
        fig.add_trace(go.Scatter(x=x, y=df[col('sop_iCh')], name='SOP Ich',
                                  line=dict(color=C['sop_ch'], dash='dot', width=1)))
    if col('sop_iDisch') in df.columns:
        fig.add_trace(go.Scatter(x=x, y=-df[col('sop_iDisch')], name='SOP Idch',
                                  line=dict(color=C['sop_dch'], dash='dot', width=1)))
    figs['current'] = fig

    # 4. SOC & SOH
    fig = _fig('State of Charge & Health', '%')
    if col('soc') in df.columns:
        fig.add_trace(go.Scatter(x=x, y=df[col('soc')], name='SOC', fill='tozeroy',
                                  line=dict(color=C['soc'], width=2),
                                  fillcolor='rgba(41,128,185,0.1)'))
    if col('soh') in df.columns:
        fig.add_trace(go.Scatter(x=x, y=df[col('soh')], name='SOH',
                                  line=dict(color=C['soh'], width=2, dash='dash')))
    fig.update_yaxes(range=[0, 100])
    figs['soc'] = fig

    # 5. Cell Voltages
    # Floor sits above observed comm-glitch reads (~1000-1200 mV) and well
    # below any real Li-ion cell voltage (never legitimately under ~2500 mV
    # while the pack is connected and logging).
    fig = _fig('Cell Voltages', 'mV')
    if col('vcell_vcellMax') in df.columns:
        fig.add_trace(go.Scatter(x=x, y=_drop_below(df[col('vcell_vcellMax')], 2000), name='Max',
                                  line=dict(color=C['cell_max'], width=1.5)))
    if col('vcell_vcellMin') in df.columns:
        fig.add_trace(go.Scatter(x=x, y=_drop_below(df[col('vcell_vcellMin')], 2000), name='Min',
                                  line=dict(color=C['cell_min'], width=1.5)))
    if col('vcell_vcellAvg') in df.columns:
        fig.add_trace(go.Scatter(x=x, y=_drop_below(df[col('vcell_vcellAvg')], 2000), name='Avg',
                                  line=dict(color=C['muted'], width=1, dash='dot')))
    if col('vcell_corrected_vcell') in df.columns:
        fig.add_trace(go.Scatter(x=x, y=_drop_below(df[col('vcell_corrected_vcell')], 2000), name='Corrected',
                                  line=dict(color=C['cell_corr'], width=2, dash='dash')))
    figs['vcell'] = fig

    # 6. Temperatures
    # Floor sits just above 0 to catch a literal-0 comm glitch. This system
    # runs indoors with no sub-zero readings observed (cfg.ini only defines
    # a *high* temp alert threshold) — genuinely cold deployments would need
    # a lower/no floor here.
    fig = _fig('Temperatures', '°C')
    if col('temperature_tempMax') in df.columns:
        fig.add_trace(go.Scatter(x=x, y=_drop_below(df[col('temperature_tempMax')], 1), name='Max',
                                  line=dict(color=C['temp_max'], width=2)))
    if col('temperature_tempMin') in df.columns:
        fig.add_trace(go.Scatter(x=x, y=_drop_below(df[col('temperature_tempMin')], 1), name='Min',
                                  line=dict(color=C['temp_min'], width=1.5)))
    if col('temperature_tempAmb') in df.columns:
        fig.add_trace(go.Scatter(x=x, y=_drop_below(df[col('temperature_tempAmb')], 1), name='Ambient',
                                  line=dict(color=C['temp_amb'], dash='dot', width=1.5)))
    if col('temperature_tempPCB') in df.columns:
        fig.add_trace(go.Scatter(x=x, y=_drop_below(df[col('temperature_tempPCB')], 1), name='PCB',
                                  line=dict(color=C['temp_pcb'], dash='dot', width=1)))
    figs['temp'] = fig

    # 6b. Battery State — combined operating-state / severity indicator,
    # rendered as a single-lane timeline (one colored block per contiguous
    # segment) rather than a line, so a brief state is never lost under a
    # long one.
    state_series = _state_label_series(df, col)
    segments = _state_segments(x, state_series) if state_series is not None else []
    if segments:
        fig = _fig('Battery State', '')
        fig.add_trace(go.Bar(
            base=[s['start'] for s in segments],
            x=[s['end'] - s['start'] for s in segments],
            y=['State'] * len(segments),
            orientation='h',
            marker=dict(color=[STATE_COLORS.get(s['label'], C['muted']) for s in segments], line=dict(width=0)),
            text=[s['label'] for s in segments],
            textposition='inside',
            insidetextanchor='middle',
            hovertext=[
                f"{s['label']}<br>{s['start']:%Y-%m-%d %H:%M:%S} → {s['end']:%Y-%m-%d %H:%M:%S}"
                for s in segments
            ],
            hoverinfo='text',
            showlegend=False,
        ))
        # Bar's marker.color array has no legend of its own — add one
        # zero-size swatch per state actually present, in first-seen order.
        for label in dict.fromkeys(s['label'] for s in segments):
            fig.add_trace(go.Scatter(
                x=[None], y=[None], mode='markers',
                marker=dict(size=10, symbol='square', color=STATE_COLORS.get(label, C['muted'])),
                name=label, showlegend=True,
            ))
        fig.update_xaxes(type='date')
        fig.update_yaxes(visible=False)
        fig.update_layout(bargap=0)
        figs['state'] = fig

    # 7. Dispersion (per-string only — pack-level home data has no dispersion section)
    if col('dispersion_dispersionMax') in df.columns:
        fig = _fig('Cell Dispersion', 'mV')
        fig.add_trace(go.Scatter(x=x, y=df[col('dispersion_dispersionMax')], name='Max',
                                  line=dict(color=C['cell_max'], width=1.5)))
        if col('dispersion_dispersionMin') in df.columns:
            fig.add_trace(go.Scatter(x=x, y=df[col('dispersion_dispersionMin')], name='Min',
                                      line=dict(color=C['cell_min'], width=1.5)))
        if col('dispersion_dispersionAvg') in df.columns:
            fig.add_trace(go.Scatter(x=x, y=df[col('dispersion_dispersionAvg')], name='Avg',
                                      line=dict(color=C['muted'], width=1, dash='dot')))
        figs['dispersion'] = fig

    return figs
