"""Dash/Bootstrap rendering only. Numbers come from domain.stats.SessionStats
and domain.cycle_analysis.Cycle — this module never computes them, only
formats and colors them."""

from dash import dcc, html
import dash_bootstrap_components as dbc
import pandas as pd

from batterylogger.adapters.inbound.dash_ui.charts import create_figures
from batterylogger.domain.cycle_analysis import Cycle
from batterylogger.domain.stats import SessionStats, compute_session_stats
from batterylogger.domain.string_reading import detect_string_ids


def _info_item(label: str, value: str, mono: bool = False) -> html.Div:
    val_class = 'fw-semibold font-monospace small' if mono else 'fw-semibold'
    return html.Div([
        html.Span(label, className='text-muted small d-block', style={'fontSize': '0.72rem', 'letterSpacing': '0.04em', 'textTransform': 'uppercase'}),
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

                dbc.Col([
                    html.Div([
                        html.Span('BATTERY SPECS', className='text-muted d-block mb-2',
                                  style={'fontSize': '0.72rem', 'letterSpacing': '0.06em',
                                         'textTransform': 'uppercase', 'fontWeight': '600'}),
                        html.Div([
                            _info_item('Topology', f'{strings} string × {modules} modules' if strings else '—'),
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


def build_session_stats(stats: SessionStats) -> html.Div:
    row1, row2 = [], []

    if stats.duration_str is not None:
        row1.append(_stat_card('bi-clock', 'Duration', stats.duration_str, '#2980B9'))

    row1.append(_stat_card('bi-table', 'Records', f'{stats.record_count:,}', '#27AE60'))

    if stats.soc_min is not None and stats.soc_max is not None:
        row1.append(_stat_card('bi-battery-half', 'SOC Range', f'{stats.soc_min:.1f}% – {stats.soc_max:.1f}%', '#8E44AD'))

    if stats.max_temp is not None:
        row1.append(_stat_card('bi-thermometer-high', 'Max Temp', f'{stats.max_temp:.1f} °C', '#E74C3C'))

    if stats.peak_charge_a is not None:
        row1.append(_stat_card('bi-arrow-up-circle', 'Peak Charge', f'{stats.peak_charge_a:.1f} A', '#27AE60'))

    if stats.peak_discharge_a is not None:
        row1.append(_stat_card('bi-arrow-down-circle', 'Peak Discharge', f'{stats.peak_discharge_a:.1f} A', '#E74C3C'))

    if stats.max_cell_v is not None:
        row2.append(_stat_card('bi-chevron-double-up', 'Max Cell V', f'{stats.max_cell_v:.0f} mV', '#E74C3C'))

    if stats.min_cell_v is not None:
        row2.append(_stat_card('bi-chevron-double-down', 'Min Cell V', f'{stats.min_cell_v:.0f} mV', '#3498DB'))

    if stats.max_cell_spread_mv is not None:
        row2.append(_stat_card('bi-arrows-expand', 'Max Cell Spread', f'{stats.max_cell_spread_mv:.0f} mV', '#F39C12'))

    if stats.biggest_soc_jump_pct is not None:
        row2.append(_stat_card('bi-lightning', 'Biggest SOC Jump', f'{stats.biggest_soc_jump_pct:.2f}%', '#9B59B6'))

    if stats.max_pack_ir is not None:
        row2.append(_stat_card('bi-activity', 'Max Pack IR', f'{stats.max_pack_ir:.1f} mΩ', '#795548'))

    if stats.max_temp_spread is not None:
        row2.append(_stat_card('bi-thermometer-half', 'Max Temp Spread', f'{stats.max_temp_spread:.1f} °C', '#E67E22'))

    return html.Div([
        dbc.Row(row1, className='g-2 mb-2'),
        dbc.Row(row2, className='g-2 mb-3'),
    ])


def build_cycle_table(cycles: list[Cycle]) -> dbc.Card | None:
    if not cycles:
        return None

    DCH_COLOR = '#E74C3C'
    CH_COLOR = '#27AE60'
    DCH_BG = 'rgba(231,76,60,0.04)'
    CH_BG = 'rgba(39,174,96,0.04)'
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
        _th('#', '3%'),
        _th('Type', '10%'),
        _th('Period', '20%'),
        _th('Duration', '8%'),
        _th('SOC Start', '8%', 'right'),
        _th('SOC End', '8%', 'right'),
        _th('ΔSOC', '6%', 'right'),
        _th('Ah Total', '8%', 'right'),
        _th('Ah (∫I·dt)', '8%', 'right'),
        _th('Theo. Ah', '8%', 'right'),
        _th('Match', '6%', 'right'),
        _th('Note', '6%'),
    ]
    header = html.Thead(html.Tr(th_cells, style={'borderBottom': '2px solid #ECF0F1'}))

    rows = []
    for c in cycles:
        is_dch = c.kind == 'discharge'
        color = DCH_COLOR if is_dch else CH_COLOR
        bg = DCH_BG if is_dch else CH_BG
        icon = '↓' if is_dch else '↑'
        label = 'Discharge' if is_dch else 'Charge'
        ah_total = c.ah

        date_str = c.t_start.strftime('%Y-%m-%d')
        period = f"{date_str}   {c.t_start.strftime('%H:%M')} → {c.t_end.strftime('%H:%M')}"

        match = (ah_total / c.theo_ah * 100.0) if (c.theo_ah and c.theo_ah > 0 and not c.note) else None
        if match is not None:
            m_color = '#27AE60' if match >= 95 else ('#F39C12' if match >= 85 else '#E74C3C')
            match_td = html.Td(f'{match:.1f}%', style={'textAlign': 'right', 'color': m_color, 'fontWeight': '600', 'verticalAlign': 'middle'})
        else:
            match_td = html.Td('—', style={'textAlign': 'right', 'color': '#BDC3C7', 'verticalAlign': 'middle'})

        theo_str = f"{c.theo_ah:.1f}" if c.theo_ah is not None else '—'

        td_cells = [
            html.Td(c.n, style={'color': '#95A5A6', 'verticalAlign': 'middle'}),
            html.Td(
                dbc.Badge([html.Span(icon, style={'marginRight': '4px'}), label],
                          style={'backgroundColor': color, 'fontSize': '0.7rem'}),
                style={'verticalAlign': 'middle'},
            ),
            html.Td(html.Span(period, className='font-monospace', style={'fontSize': '0.8rem'}),
                    style={'verticalAlign': 'middle'}),
            html.Td(html.Span(c.duration, className='font-monospace'),
                    style={'verticalAlign': 'middle'}),
            html.Td(f"{c.soc_start:.1f}%", style={'textAlign': 'right', 'verticalAlign': 'middle'}),
            html.Td(f"{c.soc_end:.1f}%", style={'textAlign': 'right', 'verticalAlign': 'middle'}),
            html.Td(f"{c.delta_soc:.1f}%", style={'textAlign': 'right', 'verticalAlign': 'middle'}),
            html.Td(f"{ah_total:.1f} Ah",
                    style={'textAlign': 'right', 'fontWeight': '600', 'verticalAlign': 'middle'}),
        ]

        ah_calc_str = f"{c.ah_calc:.1f} Ah" if c.ah_calc is not None else '—'
        td_cells += [
            html.Td(ah_calc_str, style={'textAlign': 'right', 'color': '#8E44AD', 'fontWeight': '600', 'verticalAlign': 'middle'}),
            html.Td(f"{theo_str} Ah", style={'textAlign': 'right', 'color': '#7F8C8D', 'verticalAlign': 'middle'}),
            match_td,
            html.Td(
                html.Span(c.note, style={'fontSize': '0.72rem', 'color': '#95A5A6'})
                if c.note else html.Span('—', style={'color': '#BDC3C7'}),
                style={'verticalAlign': 'middle'},
            ),
        ]
        rows.append(html.Tr(td_cells, style={'backgroundColor': bg}))

    useful_cap = cycles[0].useful_capacity
    nominal_cap = cycles[0].nominal_capacity
    complete = sum(1 for c in cycles if not c.note)

    caption_parts = [
        'Ah (BMS): BMS internal coulomb counter  ·  Ah (∫I·dt): manual integration of logged current × Δt  ·  Theo. Ah: Useful Capacity × ΔSOC / 100',
        f'Useful Capacity: {useful_cap:.0f} Ah  ·  Match uses Ah vs Theo. Ah  ·  only cycles ≥ 50% ΔSOC shown',
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


def _string_graph(prefix: str, key: str, figs: dict):
    return dcc.Graph(
        id={'type': 'string-graph', 'index': f'{prefix}{key}'},
        figure=figs[key],
        config={'displayModeBar': True, 'modeBarButtonsToRemove': ['lasso2d', 'select2d']},
    )


def build_string_tabs(df: pd.DataFrame) -> dbc.Tabs | None:
    """One tab per discovered string, each with its own stat cards + charts.

    Returns None for old-format logs (no `string{N}_soc` columns) — fully
    additive, doesn't touch the existing pack-level dashboard.
    """
    string_ids = detect_string_ids(df)
    if not string_ids:
        return None

    tabs = []
    for sid in string_ids:
        prefix = f'string{sid}_'
        stats = compute_session_stats(df, prefix=prefix)
        figs = create_figures(df, prefix=prefix)

        tab_content = html.Div([
            build_session_stats(stats),
            dbc.Row([
                dbc.Col(_string_graph(prefix, 'power', figs), md=6),
                dbc.Col(_string_graph(prefix, 'voltage', figs), md=6),
            ], className='mb-3'),
            dbc.Row([
                dbc.Col(_string_graph(prefix, 'soc', figs), md=6),
                dbc.Col(_string_graph(prefix, 'current', figs), md=6),
            ], className='mb-3'),
            dbc.Row([
                dbc.Col(_string_graph(prefix, 'vcell', figs), md=6),
                dbc.Col(_string_graph(prefix, 'temp', figs), md=6),
            ], className='mb-3'),
        ] + ([
            dbc.Row([dbc.Col(_string_graph(prefix, 'dispersion', figs), md=6)], className='mb-3'),
        ] if 'dispersion' in figs else []) + ([
            dbc.Row([dbc.Col(_string_graph(prefix, 'state', figs), md=12)], className='mb-3'),
        ] if 'state' in figs else []), className='pt-3')

        tabs.append(dbc.Tab(tab_content, label=f'String {sid}', tab_id=f'string-tab-{sid}'))

    return dbc.Tabs(tabs, className='mt-2')
