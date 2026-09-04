"""Dash app factory — wires layout + callbacks together."""

import dash
import dash_bootstrap_components as dbc

from batterylogger.adapters.inbound.dash_ui.callbacks import register_callbacks
from batterylogger.adapters.inbound.dash_ui.layout import build_layout
from batterylogger.application.analysis_service import AnalysisUseCase


def create_app(analysis_use_case: AnalysisUseCase) -> dash.Dash:
    app = dash.Dash(
        __name__,
        external_stylesheets=[dbc.themes.FLATLY, dbc.icons.BOOTSTRAP],
        suppress_callback_exceptions=True,
        title="Battery Log Analyzer",
    )
    app.layout = build_layout()
    register_callbacks(app, analysis_use_case)
    return app
