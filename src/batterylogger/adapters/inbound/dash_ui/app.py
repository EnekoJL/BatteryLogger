"""Dash app factory — wires layout + callbacks together."""

import dash
import dash_bootstrap_components as dbc
import diskcache

from batterylogger.adapters.inbound.dash_ui.callbacks import register_callbacks
from batterylogger.adapters.inbound.dash_ui.layout import build_layout
from batterylogger.application.analysis_service import AnalysisUseCase

# A background callback manager is required for the CSV-upload progress bar
# (register_callbacks' update_store runs as background=True so it can push
# live progress via set_progress mid-parse — a plain callback can only
# return once, at the very end). diskcache is a local file-based cache, no
# extra service to run — appropriate for this single-user local app.
_CACHE = diskcache.Cache('./.dash_cache')
_BACKGROUND_CALLBACK_MANAGER = dash.DiskcacheManager(_CACHE)


def create_app(analysis_use_case: AnalysisUseCase) -> dash.Dash:
    app = dash.Dash(
        __name__,
        # Manrope is self-hosted via assets/fonts.css (Dash auto-serves
        # assets/) rather than pulled from Google Fonts, so the chart font
        # doesn't depend on the deployment machine having internet access.
        external_stylesheets=[dbc.themes.FLATLY, dbc.icons.BOOTSTRAP],
        suppress_callback_exceptions=True,
        title="Battery Log Analyzer",
        background_callback_manager=_BACKGROUND_CALLBACK_MANAGER,
    )
    app.layout = build_layout()
    register_callbacks(app, analysis_use_case)
    return app
