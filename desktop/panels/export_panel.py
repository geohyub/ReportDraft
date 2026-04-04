"""Export panel for ProcessingReportDraft."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QComboBox,
    QFileDialog,
    QTextBrowser,
    QListWidget,
)


class ExportPanel(QWidget):
    panel_title = "Export"

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        status = QGroupBox("Export summary")
        status_layout = QVBoxLayout(status)
        self.summary = QTextBrowser()
        self.summary.setMinimumHeight(120)
        status_layout.addWidget(self.summary)
        root.addWidget(status)

        form_box = QGroupBox("Output")
        form_layout = QFormLayout(form_box)
        self.output_dir = QLineEdit(self.controller.output_dir)
        self.output_file = QLineEdit()
        self._filename_manual = False
        self.format = QComboBox()
        self.format.addItems(["docx", "excel", "html", "json", "text", "bulk docx"])
        self.format.currentTextChanged.connect(self._refresh_filename)
        self.output_file.textEdited.connect(self._mark_filename_manual)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_output_dir)
        dir_row = QHBoxLayout()
        dir_row.addWidget(self.output_dir)
        dir_row.addWidget(browse_btn)
        form_layout.addRow("Output folder", dir_row)
        form_layout.addRow("Format", self.format)
        form_layout.addRow("File name", self.output_file)

        btn_row = QHBoxLayout()
        self.export_btn = QPushButton("Export now")
        self.bulk_btn = QPushButton("Generate all templates")
        self.open_btn = QPushButton("Open folder")
        self.refresh_btn = QPushButton("Refresh summary")
        for btn in (self.export_btn, self.bulk_btn, self.open_btn, self.refresh_btn):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_row.addWidget(btn)
        form_layout.addRow(btn_row)
        root.addWidget(form_box)

        self.log = QListWidget()
        root.addWidget(self.log)

        self.export_btn.clicked.connect(self._export_current)
        self.bulk_btn.clicked.connect(self._export_all)
        self.open_btn.clicked.connect(self._open_folder)
        self.refresh_btn.clicked.connect(self._refresh)
        self.controller.flow_changed.connect(self.refresh_flow)
        self.controller.activity_logged.connect(self._append_log)
        self.refresh_flow(self.controller.current_flow)

    def _refresh(self):
        self.refresh_flow(self.controller.current_flow)

    def _browse_output_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "Select output folder", self.output_dir.text())
        if folder:
            self.output_dir.setText(folder)
            self.controller.set_output_dir(folder)
            self._refresh_filename()

    def _refresh_filename(self, *_):
        flow = self.controller.current_flow
        fmt = self.format.currentText()
        if fmt == "bulk docx":
            self.output_file.setText("")
            self.output_file.setPlaceholderText("Folder export only")
            self.output_file.setEnabled(False)
            self._filename_manual = False
        else:
            self.output_file.setEnabled(True)
            self.output_file.setPlaceholderText("Leave blank to use default name")
            if not self._filename_manual or not self.output_file.text().strip():
                self.output_file.setText(self.controller.exporter.default_filename(flow, fmt))
                self._filename_manual = False

    def _mark_filename_manual(self, *_):
        self._filename_manual = True

    def _append_log(self, text: str, level: str):
        prefix = {
            "success": "✓",
            "warning": "!",
            "error": "×",
            "info": "•",
        }.get(level, "•")
        self.log.insertItem(0, f"{prefix} {text}")
        while self.log.count() > 10:
            self.log.takeItem(self.log.count() - 1)

    def refresh_flow(self, flow):
        context = self.controller.report.build_preview_bundle(flow)["context"]
        self.summary.setHtml(
            f"<h3>{context['readiness']['label']}</h3>"
            f"<p>{context['readiness']['detail']}</p>"
            f"<p><strong>Project:</strong> {flow.project_name or 'TBD'}<br>"
            f"<strong>Type:</strong> {flow.data_type}<br>"
            f"<strong>Steps:</strong> {flow.step_count}</p>"
        )
        self._refresh_filename()

    def _export_current(self):
        out_dir = Path(self.output_dir.text().strip() or self.controller.output_dir)
        fmt = self.format.currentText()
        if fmt == "bulk docx":
            self._export_all()
            return
        file_name = self.output_file.text().strip() or self.controller.exporter.default_filename(self.controller.current_flow, fmt)
        saved = self.controller.export_flow(str(out_dir / file_name), fmt)
        self._append_log(f"Saved {Path(saved).name}", "success")

    def _export_all(self):
        out_dir = Path(self.output_dir.text().strip() or self.controller.output_dir)
        saved = self.controller.export_all_templates(str(out_dir))
        self._append_log(f"Generated {len(saved)} template files", "success")

    def _open_folder(self):
        out_dir = Path(self.output_dir.text().strip() or self.controller.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        import subprocess, sys

        if sys.platform == "win32":
            subprocess.Popen(["explorer", str(out_dir)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(out_dir)])
        else:
            subprocess.Popen(["xdg-open", str(out_dir)])
