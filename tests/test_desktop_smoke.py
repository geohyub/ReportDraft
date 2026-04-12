"""Offscreen smoke tests for the ProcessingReportDraft PySide6 shell."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).parent.parent))

from desktop.main import ProcessingReportDraftApp


@pytest.fixture(scope="module")
def app():
    qt_app = QApplication.instance()
    if qt_app is None:
        qt_app = QApplication([])
    yield qt_app


def test_desktop_shell_loads_template_and_exports(tmp_path, app):
    window = ProcessingReportDraftApp()
    window.controller.load_template(
        "MBES",
        {
            "project_name": "Smoke Project",
            "client": "GeoView",
            "vessel": "Vessel A",
            "area": "Test Area",
            "line_count": 12,
        },
    )
    app.processEvents()

    window.sidebar.set_active_panel("preview")
    app.processEvents()
    assert "Smoke Project" in window.preview_panel.overview.toHtml()

    output = tmp_path / "smoke_report.docx"
    saved = window.controller.export_flow(str(output), "docx")
    assert Path(saved).exists()
    assert Path(saved).stat().st_size > 1000


def test_dashboard_and_editor_refresh(app):
    window = ProcessingReportDraftApp()
    window.sidebar.set_active_panel("editor")
    app.processEvents()
    sample = window.controller.data.sample_log_text(window.controller.current_flow)
    window.editor_panel.log_editor.setPlainText(sample)
    window.editor_panel._parse_log()
    app.processEvents()
    assert window.controller.current_flow.step_count > 0
    window.sidebar.set_active_panel("dashboard")
    app.processEvents()
    assert window.dashboard_panel.cards[1]._value_label.text() == str(window.controller.current_flow.step_count)


def test_export_panel_operator_packet_and_save(tmp_path, app):
    window = ProcessingReportDraftApp()
    window.sidebar.set_active_panel("export")
    app.processEvents()

    packet_html = window.export_panel.packet.toHtml().lower()
    assert "operator packet" in packet_html or "readiness" in packet_html
    assert "author / reviewer handoff" in packet_html
    assert "template comparison" in packet_html
    assert "sign-off readiness" in packet_html

    window.export_panel.output_dir.setText(str(tmp_path))
    window.export_panel._refresh_packet()
    window.export_panel._export_packet("json")
    app.processEvents()

    saved = list(tmp_path.glob("*_OperatorPacket.json"))
    assert saved
    assert saved[0].stat().st_size > 100
