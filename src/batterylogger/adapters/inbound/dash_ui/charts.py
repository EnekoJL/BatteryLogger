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
    fig = _fig('Battery Voltage', 'V')
    if col('voltage') in df.columns:
        fig.add_trace(go.Scatter(x=x, y=df[col('voltage')], name='Voltage',
                                  line=dict(color=C['voltage'], width=2)))
    if col('sop_vCh') in df.columns:
        fig.add_trace(go.Scatter(x=x, y=df[col('sop_vCh')], name='SOP Vch',
                                  line=dict(color=C['sop_ch'], dash='dot', width=1)))
    if col('sop_vDisch') in df.columns:
        fig.add_trace(go.Scatter(x=x, y=df[col('sop_vDisch')], name='SOP Vdch',
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
    fig = _fig('Cell Voltages', 'mV')
    if col('vcell_vcellMax') in df.columns:
        fig.add_trace(go.Scatter(x=x, y=df[col('vcell_vcellMax')], name='Max',
                                  line=dict(color=C['cell_max'], width=1.5)))
    if col('vcell_vcellMin') in df.columns:
        fig.add_trace(go.Scatter(x=x, y=df[col('vcell_vcellMin')], name='Min',
                                  line=dict(color=C['cell_min'], width=1.5)))
    if col('vcell_vcellAvg') in df.columns:
        fig.add_trace(go.Scatter(x=x, y=df[col('vcell_vcellAvg')], name='Avg',
                                  line=dict(color=C['muted'], width=1, dash='dot')))
    if col('vcell_corrected_vcell') in df.columns:
        fig.add_trace(go.Scatter(x=x, y=df[col('vcell_corrected_vcell')], name='Corrected',
                                  line=dict(color=C['cell_corr'], width=2, dash='dash')))
    figs['vcell'] = fig

    # 6. Temperatures
    fig = _fig('Temperatures', '°C')
    if col('temperature_tempMax') in df.columns:
        fig.add_trace(go.Scatter(x=x, y=df[col('temperature_tempMax')], name='Max',
                                  line=dict(color=C['temp_max'], width=2)))
    if col('temperature_tempMin') in df.columns:
        fig.add_trace(go.Scatter(x=x, y=df[col('temperature_tempMin')], name='Min',
                                  line=dict(color=C['temp_min'], width=1.5)))
    if col('temperature_tempAmb') in df.columns:
        fig.add_trace(go.Scatter(x=x, y=df[col('temperature_tempAmb')], name='Ambient',
                                  line=dict(color=C['temp_amb'], dash='dot', width=1.5)))
    if col('temperature_tempPCB') in df.columns:
        fig.add_trace(go.Scatter(x=x, y=df[col('temperature_tempPCB')], name='PCB',
                                  line=dict(color=C['temp_pcb'], dash='dot', width=1)))
    figs['temp'] = fig

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
