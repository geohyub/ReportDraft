"""PySide6 desktop shell for ProcessingReportDraft."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = str(Path(__file__).resolve().parents[1])
_SHARED = str(Path(__file__).resolve().parents[3] / "_shared")
for path in (_ROOT, _SHARED):
    if path not in sys.path:
        sys.path.insert(0, path)

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton

from geoview_pyside6 import GeoViewApp, Category

from desktop.app_controller import DraftController
from desktop.panels.dashboard_panel import DashboardPanel
from desktop.panels.template_panel import TemplatePanel
from desktop.panels.editor_panel import EditorPanel
from desktop.panels.preview_panel import PreviewPanel
from desktop.panels.export_panel import ExportPanel


class ProcessingReportDraftApp(GeoViewApp):
    APP_NAME = "ProcessingReportDraft"
    APP_VERSION = "v1.0.0"
    CATEGORY = Category.MANAGEMENT

    def __init__(self):
        self.controller = DraftController()
        super().__init__()
        self.controller.activity_logged.connect(self._log_to_status)
        self.controller.flow_changed.connect(self._on_flow_changed)
        self.controller.flow_changed.emit(self.controller.current_flow)

    def setup_panels(self):
        self.dashboard_panel = DashboardPanel(self.controller)
        self.template_panel = TemplatePanel(self.controller)
        self.editor_panel = EditorPanel(self.controller)
        self.preview_panel = PreviewPanel(self.controller)
        self.export_panel = ExportPanel(self.controller)

        self.add_panel("dashboard", "D", "Overview", self.dashboard_panel)
        self.add_panel("template", "T", "Templates", self.template_panel)
        self.add_sidebar_separator("Workflow")
        self.add_panel("editor", "E", "Editor", self.editor_panel)
        self.add_panel("preview", "P", "Preview", self.preview_panel)
        self.add_sidebar_separator("Output")
        self.add_panel("export", "X", "Export", self.export_panel)

    def _log_to_status(self, text: str, level: str):
        self.status_bar.showMessage(text, 3500)

    def _on_flow_changed(self, flow):
        self.setWindowTitle(f"{self.APP_NAME} {self.APP_VERSION} — {flow.data_type}")

    def _clear_topbar(self):
        while self.top_bar.actions_layout.count():
            item = self.top_bar.actions_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _add_button(self, text: str, callback, primary: bool = False):
        btn = QPushButton(text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setObjectName("primaryButton" if primary else "secondaryButton")
        btn.clicked.connect(callback)
        self.top_bar.actions_layout.addWidget(btn)

    def _switch_panel(self, panel_id: str):
        super()._switch_panel(panel_id)
        self._clear_topbar()
        if panel_id == "dashboard":
            self._add_button("Load Template", lambda: self.sidebar.set_active_panel("template"))
            self._add_button("Parse Log", lambda: self.sidebar.set_active_panel("editor"))
            self._add_button("Preview", lambda: self.sidebar.set_active_panel("preview"))
        elif panel_id == "template":
            self._add_button("Apply Template", self.template_panel._load_template, primary=True)
            self._add_button("Sample Log", self.editor_panel._load_sample)
            self._add_button("Editor", lambda: self.sidebar.set_active_panel("editor"))
        elif panel_id == "editor":
            self._add_button("Parse Log", self.editor_panel._parse_log, primary=True)
            self._add_button("Preview", lambda: self.sidebar.set_active_panel("preview"))
            self._add_button("Export", lambda: self.sidebar.set_active_panel("export"))
        elif panel_id == "preview":
            self._add_button("Refresh", self.preview_panel._refresh, primary=True)
            self._add_button("Export", lambda: self.sidebar.set_active_panel("export"))
            self._add_button("Templates", lambda: self.sidebar.set_active_panel("template"))
        elif panel_id == "export":
            self._add_button("Export Now", self.export_panel._export_current, primary=True)
            self._add_button("Generate All", self.export_panel._export_all)
            self._add_button("Open Folder", self.export_panel._open_folder)


def main():
    ProcessingReportDraftApp.run()


if __name__ == "__main__":
    main()

