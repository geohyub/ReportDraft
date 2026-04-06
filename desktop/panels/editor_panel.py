"""Step editor and log parser panel."""

from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QGroupBox,
    QPlainTextEdit,
    QPushButton,
    QLineEdit,
    QTextEdit,
    QFormLayout,
    QLabel,
)

from geoview_pyside6.widgets import GVTableView


class EditorPanel(QWidget):
    panel_title = "Editor"

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self._step_data: list[list[str]] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        root.addWidget(self.status)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        left_box = QGroupBox("Processing Log")
        left_layout = QVBoxLayout(left_box)
        self.log_editor = QPlainTextEdit()
        self.log_editor.setPlaceholderText("Paste a processing log or draft note here.")
        left_layout.addWidget(self.log_editor)

        left_btns = QHBoxLayout()
        self.parse_btn = QPushButton("Parse log")
        self.sample_btn = QPushButton("Load sample")
        self.clear_log_btn = QPushButton("Clear")
        for btn in (self.parse_btn, self.sample_btn, self.clear_log_btn):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            left_btns.addWidget(btn)
        left_layout.addLayout(left_btns)
        splitter.addWidget(left_box)

        right_box = QGroupBox("Workflow Steps")
        right_layout = QVBoxLayout(right_box)
        self.step_table = GVTableView()
        self.step_table.show_empty_state(
            "No workflow steps",
            icon_name="list-ordered",
            subtitle="Parse a log or add steps manually",
        )
        right_layout.addWidget(self.step_table)

        edit_box = QGroupBox("Step editor")
        edit_layout = QFormLayout(edit_box)
        self.name = QLineEdit()
        self.stage = QLineEdit()
        self.description = QLineEdit()
        self.rationale = QLineEdit()
        self.qc_focus = QLineEdit()
        self.expected_output = QLineEdit()
        self.parameters = QTextEdit()
        self.parameters.setPlaceholderText('{"Key": "Value"}')
        for label, widget in [
            ("Name", self.name),
            ("Stage", self.stage),
            ("Description", self.description),
            ("Rationale", self.rationale),
            ("QC focus", self.qc_focus),
            ("Expected output", self.expected_output),
            ("Parameters (JSON)", self.parameters),
        ]:
            edit_layout.addRow(label, widget)

        btn_row = QHBoxLayout()
        self.add_btn = QPushButton("Add")
        self.update_btn = QPushButton("Apply")
        self.remove_btn = QPushButton("Remove")
        self.up_btn = QPushButton("Move up")
        self.down_btn = QPushButton("Move down")
        for btn in (self.add_btn, self.update_btn, self.remove_btn, self.up_btn, self.down_btn):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_row.addWidget(btn)
        edit_layout.addRow(btn_row)
        right_layout.addWidget(edit_box)
        splitter.addWidget(right_box)
        splitter.setSizes([420, 760])
        root.addWidget(splitter)

        self.parse_btn.clicked.connect(self._parse_log)
        self.sample_btn.clicked.connect(self._load_sample)
        self.clear_log_btn.clicked.connect(self.log_editor.clear)
        self.add_btn.clicked.connect(self._add_step)
        self.update_btn.clicked.connect(self._update_step)
        self.remove_btn.clicked.connect(self._remove_step)
        self.up_btn.clicked.connect(lambda: self._move_step(-1))
        self.down_btn.clicked.connect(lambda: self._move_step(+1))
        self.controller.flow_changed.connect(self.refresh_flow)
        self.refresh_flow(self.controller.current_flow)

    def _selected_order(self) -> int | None:
        idx = self.step_table.currentIndex()
        if not idx.isValid():
            return None
        proxy = self.step_table._proxy
        source_idx = proxy.mapToSource(idx) if proxy else idx
        row = source_idx.row()
        if row < 0 or row >= len(self._step_data):
            return None
        return int(self._step_data[row][0])

    def _sync_editor_from_selection(self, *args):
        idx = self.step_table.currentIndex()
        if not idx.isValid():
            return
        proxy = self.step_table._proxy
        source_idx = proxy.mapToSource(idx) if proxy else idx
        row = source_idx.row()
        if row < 0 or row >= len(self._step_data):
            return
        data = self._step_data[row]
        self.name.setText(data[2])       # Name
        self.stage.setText(data[1])      # Stage
        self.description.setText(data[3]) # Description
        self.qc_focus.setText(data[4])   # QC Focus
        self.expected_output.setText(data[5])  # Expected Output
        order = int(data[0])
        step = next((s for s in self.controller.current_flow.steps if s.order == order), None)
        self.rationale.setText(getattr(step, "rationale", ""))
        try:
            params = getattr(step, "parameters", {}) or {}
            self.parameters.setPlainText(json.dumps(params, indent=2, ensure_ascii=False))
        except Exception:
            self.parameters.setPlainText("{}")

    def _parse_log(self):
        self.controller.parse_log(self.log_editor.toPlainText())

    def _load_sample(self):
        self.log_editor.setPlainText(self.controller.data.sample_log_text(self.controller.current_flow))

    def _payload(self) -> dict:
        text = self.parameters.toPlainText().strip()
        params = {}
        if text:
            try:
                params = json.loads(text)
                if not isinstance(params, dict):
                    raise ValueError("Parameters must be a JSON object")
            except Exception as exc:
                from geoview_pyside6.widgets.confirm_dialog import ConfirmDialog
                ConfirmDialog("Parameters", f"Invalid JSON: {exc}",
                              confirm_text="OK", cancel_text="", dialog_type="error", parent=self).exec()
                return {}
        return {
            "name": self.name.text().strip(),
            "stage": self.stage.text().strip(),
            "description": self.description.text().strip(),
            "rationale": self.rationale.text().strip(),
            "qc_focus": self.qc_focus.text().strip(),
            "expected_output": self.expected_output.text().strip(),
            "parameters": params,
        }

    def _add_step(self):
        payload = self._payload()
        if not payload.get("name"):
            return
        order = self._selected_order()
        position = order + 1 if order else None
        self.controller.add_step(position=position, **payload)

    def _update_step(self):
        order = self._selected_order()
        if order is None:
            return
        payload = self._payload()
        if not payload.get("name"):
            return
        self.controller.update_step(order, **payload)

    def _remove_step(self):
        order = self._selected_order()
        if order is None:
            return
        self.controller.remove_step(order)

    def _move_step(self, delta: int):
        order = self._selected_order()
        if order is None:
            return
        steps = list(self.controller.current_flow.steps)
        idx = next((i for i, step in enumerate(steps) if step.order == order), None)
        if idx is None:
            return
        other = idx + delta
        if other < 0 or other >= len(steps):
            return
        steps[idx], steps[other] = steps[other], steps[idx]
        self.controller.reorder_steps([step.order for step in steps])

    def refresh_flow(self, flow):
        context = self.controller.report.build_preview_bundle(flow)["context"]
        validation = context["validation"]
        self.status.setText(
            f"Readiness: {context['readiness']['label']} | "
            f"Validation score: {validation['score']}% | "
            f"Open items: {len(context['open_items'])}"
        )
        self._step_data = []
        for step in flow.steps:
            self._step_data.append([
                str(step.order),
                step.stage,
                step.name,
                step.description,
                step.qc_focus,
                step.expected_output,
            ])
        if self._step_data:
            self.step_table.hide_empty_state()
            self.step_table.set_data(
                ["Order", "Stage", "Name", "Description", "QC Focus", "Expected Output"],
                self._step_data,
            )
            # Reconnect selection signal after set_data creates new model
            sel_model = self.step_table.selectionModel()
            if sel_model:
                sel_model.currentRowChanged.connect(self._sync_editor_from_selection)
        else:
            self.step_table.show_empty_state(
                "No workflow steps",
                icon_name="list-ordered",
                subtitle="Parse a log or add steps manually",
            )

