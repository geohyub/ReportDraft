"""Export panel for ProcessingReportDraft."""

from __future__ import annotations

import html
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
        self._last_export_target = ""
        self._last_export_path = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        status = QGroupBox("Export summary")
        status_layout = QVBoxLayout(status)
        self.summary = QTextBrowser()
        self.summary.setMinimumHeight(120)
        status_layout.addWidget(self.summary)
        root.addWidget(status)

        packet_box = QGroupBox("Operator packet")
        packet_layout = QVBoxLayout(packet_box)
        self.packet = QTextBrowser()
        self.packet.setMinimumHeight(180)
        packet_layout.addWidget(self.packet)
        packet_btns = QHBoxLayout()
        self.packet_json_btn = QPushButton("Save packet JSON")
        self.packet_md_btn = QPushButton("Save packet Markdown")
        self.packet_txt_btn = QPushButton("Save packet Text")
        self.packet_refresh_btn = QPushButton("Refresh packet")
        for btn in (self.packet_json_btn, self.packet_md_btn, self.packet_txt_btn, self.packet_refresh_btn):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            packet_btns.addWidget(btn)
        packet_layout.addLayout(packet_btns)
        root.addWidget(packet_box)

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
        self.packet_json_btn.clicked.connect(lambda: self._export_packet("json"))
        self.packet_md_btn.clicked.connect(lambda: self._export_packet("markdown"))
        self.packet_txt_btn.clicked.connect(lambda: self._export_packet("text"))
        self.packet_refresh_btn.clicked.connect(self._refresh_packet)
        self.controller.flow_changed.connect(self.refresh_flow)
        self.controller.activity_logged.connect(self._append_log)
        self.refresh_flow(self.controller.current_flow)

    def _refresh(self):
        self.refresh_flow(self.controller.current_flow)

    def _build_packet(self):
        return self.controller.report.build_operator_packet(
            self.controller.current_flow,
            preview_bundle=self.controller.last_preview,
            last_export_target=self._last_export_target,
            last_export_path=self._last_export_path,
        )

    def _packet_output_path(self, fmt: str) -> Path:
        out_dir = Path(self.output_dir.text().strip() or self.controller.output_dir)
        file_name = self.controller.exporter.default_packet_filename(self.controller.current_flow, fmt)
        return out_dir / file_name

    def _refresh_packet(self):
        packet = self._build_packet()
        current = packet["current_state"]
        comparison = packet["template_comparison"]
        handoff = packet["handoff_summary"]
        routing = packet["reviewer_routing"]
        signoff = packet["sign_off"]
        last_export = packet["last_export"]
        html_lines = [
            f"<h3>{html.escape(packet['title'])}</h3>",
            "<h4>Author / reviewer handoff</h4>",
            "<ul>",
            f"<li><strong>Story:</strong> {html.escape(handoff['story'])}</li>",
            f"<li><strong>Strategy:</strong> {html.escape(handoff['strategy'])}</li>",
            f"<li><strong>Change summary:</strong> {html.escape(handoff['change_summary'])}</li>",
            f"<li><strong>Attention summary:</strong> {html.escape(handoff['attention_summary'])}</li>",
            f"<li><strong>Status:</strong> {html.escape(handoff['status'])}</li>",
            f"<li><strong>Next step:</strong> {html.escape(handoff['next_step'])}</li>",
            f"<li><strong>Review check:</strong> {html.escape(handoff['review_check'])}</li>",
        ]
        if handoff["change_highlights"]:
            html_lines.append("<li><strong>Change highlights:</strong><ul>")
            html_lines.extend(f"<li>{html.escape(item)}</li>" for item in handoff["change_highlights"])
            html_lines.append("</ul></li>")
        if handoff["attention_items"]:
            html_lines.append("<li><strong>Attention items:</strong><ul>")
            html_lines.extend(f"<li>{html.escape(item)}</li>" for item in handoff["attention_items"])
            html_lines.append("</ul></li>")
        html_lines.extend([
            "</ul>",
            "<h4>Reviewer routing</h4>",
            "<ul>",
            f"<li><strong>Status:</strong> {html.escape(routing['status'])}</li>",
            f"<li><strong>Next check:</strong> {html.escape(routing['next_check'])}</li>",
            f"<li><strong>Material change summary:</strong> {html.escape(routing['material_change_summary'])}</li>",
            f"<li><strong>Reviewer message:</strong> {html.escape(routing['reviewer_message'])}</li>",
            "<li><strong>Material changes:</strong><ul>",
        ])
        html_lines.extend(f"<li>{html.escape(item)}</li>" for item in routing["material_changes"])
        html_lines.extend([
            "</ul></li>",
            "<li><strong>Pass back to author:</strong><ul>",
        ])
        if routing["author_return_items"]:
            html_lines.extend(f"<li>{html.escape(item)}</li>" for item in routing["author_return_items"])
        else:
            html_lines.append("<li>No return items; continue to sign-off.</li>")
        html_lines.extend([
            "</ul></li>",
            "</ul>",
            "<h4>Readiness</h4>",
            f"<h3>{html.escape(packet['readiness']['label'])}</h3>",
            f"<p>{html.escape(packet['readiness']['detail'])}</p>",
            "<h4>Current state</h4>",
            "<ul>",
            f"<li><strong>Project:</strong> {html.escape(packet['project_name'])}</li>",
            f"<li><strong>Client:</strong> {html.escape(packet['client'])}</li>",
            f"<li><strong>Data type:</strong> {html.escape(packet['data_type'])}</li>",
            f"<li><strong>Steps:</strong> {current['step_count']} · <strong>Stages:</strong> {current['stage_count']}</li>",
            f"<li><strong>Validation score:</strong> {current['validation_score']}%</li>",
            f"<li><strong>Open items:</strong> {current['open_items_count']}</li>",
            f"<li><strong>Placeholder parameters:</strong> {current['tbd_parameters']}</li>",
            "</ul>",
            "<h4>Sign-off readiness</h4>",
            "<ul>",
            f"<li><strong>Can sign off:</strong> {'Yes' if signoff['can_sign_off'] else 'No'}</li>",
            f"<li><strong>Needs review:</strong> {'Yes' if signoff['needs_review'] else 'No'}</li>",
        ])
        html_lines.extend(f"<li>{html.escape(item)}</li>" for item in signoff["checklist"])
        html_lines.extend([
            "</ul>",
            "<h4>Template comparison</h4>",
            "<ul>",
            f"<li><strong>Baseline:</strong> {html.escape(comparison['baseline'])}</li>",
            f"<li><strong>Status:</strong> {html.escape(comparison['status'])}</li>",
            f"<li><strong>Summary:</strong> {html.escape(comparison['summary'])}</li>",
            f"<li><strong>Step changes:</strong> +{comparison['step_changes']['added']} · -{comparison['step_changes']['removed']} · ~{comparison['step_changes']['modified']}</li>",
            f"<li><strong>Metadata changes:</strong> {comparison['metadata_changes']}</li>",
        ])
        if comparison["highlights"]:
            html_lines.extend(f"<li>{html.escape(item)}</li>" for item in comparison["highlights"])
        html_lines.extend([
            "</ul>",
            "<h4>Blocking items</h4>",
            "<ul>",
        ])
        if packet["blocking_items"]:
            html_lines.extend(f"<li>{html.escape(item)}</li>" for item in packet["blocking_items"])
        else:
            html_lines.append("<li>No blocking items detected.</li>")
        html_lines.extend([
            "</ul>",
            "<h4>Recommended next actions</h4>",
            "<ol>",
        ])
        html_lines.extend(f"<li>{html.escape(action)}</li>" for action in packet["recommended_next_actions"])
        html_lines.extend([
            "</ol>",
            "<h4>Last export</h4>",
        ])
        if last_export["available"]:
            html_lines.append(f"<p><strong>Target:</strong> {html.escape(last_export['target'] or 'TBD')}<br>")
            html_lines.append(f"<strong>Path:</strong> {html.escape(last_export['path'] or 'TBD')}</p>")
        else:
            html_lines.append("<p>No export recorded yet.</p>")
        self.packet.setHtml("".join(html_lines))

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
        self._refresh_packet()

    def _export_current(self):
        out_dir = Path(self.output_dir.text().strip() or self.controller.output_dir)
        fmt = self.format.currentText()
        if fmt == "bulk docx":
            self._export_all()
            return
        file_name = self.output_file.text().strip() or self.controller.exporter.default_filename(self.controller.current_flow, fmt)
        saved = self.controller.export_flow(str(out_dir / file_name), fmt)
        self._last_export_target = fmt
        self._last_export_path = saved
        self._refresh_packet()
        self._append_log(f"Saved {Path(saved).name}", "success")

    def _export_all(self):
        out_dir = Path(self.output_dir.text().strip() or self.controller.output_dir)
        saved = self.controller.export_all_templates(str(out_dir))
        self._last_export_target = "bulk docx"
        self._last_export_path = str(out_dir)
        self._refresh_packet()
        self._append_log(f"Generated {len(saved)} template files", "success")

    def _export_packet(self, fmt: str):
        packet = self._build_packet()
        saved = self.controller.exporter.export_operator_packet(packet, self._packet_output_path(fmt), fmt)
        self._last_export_target = f"operator packet {fmt}"
        self._last_export_path = saved
        self._refresh_packet()
        self._append_log(f"Saved operator packet {Path(saved).name}", "success")

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
