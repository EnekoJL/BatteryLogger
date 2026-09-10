"""Static Dash layout — ported verbatim from the old visual_log.py."""

from dash import dcc, html
import dash_bootstrap_components as dbc


def build_layout() -> dbc.Container:
    return dbc.Container([
        dcc.Store(id='memory-store'),
        dcc.Download(id='download-html'),

        # ── Header ──────────────────────────────────────────────────────────
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

        # ── Upload ──────────────────────────────────────────────────────────
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

        # ── Action bar ──────────────────────────────────────────────────────
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
        ], className='mb-2 align-items-center'),

        html.Hr(className='my-2'),

        # ── Dynamic content ─────────────────────────────────────────────────
        dbc.Spinner(
            html.Div(id='output-graphs'),
            color='primary',
            spinner_style={'width': '2rem', 'height': '2rem'},
        ),

    ], fluid=True, className='px-4')
