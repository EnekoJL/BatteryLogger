"""Dash callbacks — driving adapter. Delegates parsing/analysis to
AnalysisUseCase, then hands the results to charts.py/components.py for
rendering. No business logic lives in this file.

Callback bodies are plain top-level functions (explicit `analysis_use_case`
param) rather than closures, so tests can call them directly without
spinning up a Dash server or poking at app.callback_map.
"""

import copy
from functools import partial

import dash
from dash import ALL, Input, Output, State, callback_context, dcc, html
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.io as pio

from batterylogger.application.analysis_service import AnalysisUseCase
from batterylogger.adapters.inbound.dash_ui import components
from batterylogger.adapters.inbound.dash_ui.charts import create_figures


def update_store(analysis_use_case: AnalysisUseCase, contents, filename):
    if contents is None:
        return None, '', {'display': 'none'}, ''

    df, error = analysis_use_case.parse(contents, filename)
    if error:
        return (
            None,
            dbc.Alert(f'Error: {error}', color='danger', className='py-2 mt-1'),
            {'display': 'none'},
            '',
        )

    data = df.to_dict('records')
    ts = pd.to_datetime(df['Timestamp']) if 'Timestamp' in df.columns else None
    date_str = ts.min().strftime('%Y-%m-%d') if ts is not None else ''

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

    return data, filename_hint, {'display': 'inline-block'}, badge


def update_graphs(analysis_use_case: AnalysisUseCase, data):
    if data is None:
        return html.Div([
            html.Div([
                html.I(className='bi bi-bar-chart-line text-muted', style={'fontSize': '3rem'}),
                html.P('Upload a CSV log file to begin analysis.', className='text-muted mt-2'),
            ], className='text-center py-5'),
        ])

    df = pd.DataFrame(data)
    figs = create_figures(df)
    result = analysis_use_case.analyze(df)

    first_row = df.iloc[0].to_dict() if len(df) > 0 else {}
    device_panel = components.build_device_info_panel(first_row)
    session_stats = components.build_session_stats(result.stats)
    cycle_table = components.build_cycle_table(result.cycles)

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

        dbc.Row([
            dbc.Col(graph('power'), md=6),
            dbc.Col(graph('voltage'), md=6),
        ], className='mb-3'),

        dbc.Row([
            dbc.Col(graph('soc'), md=6),
            dbc.Col(graph('current'), md=6),
        ], className='mb-3'),

        dbc.Row([
            dbc.Col(graph('vcell'), md=6),
            dbc.Col(graph('temp'), md=6),
        ], className='mb-3'),

        dbc.Row([dbc.Col(graph('state'), md=12)], className='mb-3') if 'state' in figs else html.Div(),

        components.build_string_tabs(df) or html.Div(),
    ])


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


def download_html_report(data):
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


def register_callbacks(app: dash.Dash, analysis_use_case: AnalysisUseCase) -> None:
    app.callback(
        [Output('memory-store', 'data'),
         Output('output-filename', 'children'),
         Output('btn-download-html', 'style'),
         Output('header-badge', 'children')],
        Input('upload-data', 'contents'),
        State('upload-data', 'filename'),
    )(partial(update_store, analysis_use_case))

    app.callback(
        Output('output-graphs', 'children'),
        Input('memory-store', 'data'),
    )(partial(update_graphs, analysis_use_case))

    app.callback(
        Output({'type': 'dynamic-graph', 'index': ALL}, 'figure'),
        Input({'type': 'dynamic-graph', 'index': ALL}, 'relayoutData'),
        State({'type': 'dynamic-graph', 'index': ALL}, 'figure'),
    )(sync_zoom)

    app.callback(
        Output('download-html', 'data'),
        Input('btn-download-html', 'n_clicks'),
        State('memory-store', 'data'),
        prevent_initial_call=True,
    )(download_html_report)
