"""Template browser and metadata form."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QComboBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QSizePolicy,
)


class TemplatePanel(QWidget):
    panel_title = "Templates"

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        form_box = QGroupBox("Draft Metadata")
        form_layout = QFormLayout(form_box)
        self.data_type = QComboBox()
        self.data_type.addItems(["SBP", "UHR", "MBES", "MAG", "SSS"])
        self.project_name = QLineEdit()
        self.client = QLineEdit()
        self.vessel = QLineEdit()
        self.area = QLineEdit()
        self.software = QLineEdit()
        self.software.setPlaceholderText("Optional")
        self.software_version = QLineEdit()
        self.date = QLineEdit()
        self.line_count = QSpinBox()
        self.line_count.setRange(0, 99999)
        self.notes = QLineEdit()
        self.notes.setPlaceholderText("Short note for the draft")

        for label, widget in [
            ("Data type", self.data_type),
            ("Project", self.project_name),
            ("Client", self.client),
            ("Vessel", self.vessel),
            ("Area", self.area),
            ("Software", self.software),
            ("Software version", self.software_version),
            ("Date", self.date),
            ("Line count", self.line_count),
            ("Notes", self.notes),
        ]:
            form_layout.addRow(label, widget)

        self.apply_btn = QPushButton("Load template")
        self.apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        form_layout.addRow(self.apply_btn)
        top_row.addWidget(form_box, 2)

        catalog_box = QGroupBox("Template catalog")
        catalog_layout = QVBoxLayout(catalog_box)
        self.catalog = QTableWidget(0, 4)
        self.catalog.setHorizontalHeaderLabels(["Type", "Label", "Software", "Steps"])
        self.catalog.horizontalHeader().setStretchLastSection(True)
        self.catalog.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.catalog.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.catalog.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        catalog_layout.addWidget(self.catalog)
        self.template_story = QTextBrowser()
        self.template_story.setMinimumHeight(160)
        catalog_layout.addWidget(self.template_story)
        top_row.addWidget(catalog_box, 3)

        root.addLayout(top_row)

        self.apply_btn.clicked.connect(self._load_template)
        self.catalog.itemSelectionChanged.connect(self._sync_catalog_selection)
        self._populate_catalog()
        self._load_current_flow()
        self.controller.flow_changed.connect(self._load_current_flow)

    def _metadata(self) -> dict:
        return {
            "project_name": self.project_name.text().strip(),
            "client": self.client.text().strip(),
            "vessel": self.vessel.text().strip(),
            "area": self.area.text().strip(),
            "software": self.software.text().strip(),
            "software_version": self.software_version.text().strip(),
            "date": self.date.text().strip(),
            "line_count": self.line_count.value(),
            "notes": self.notes.text().strip(),
        }

    def _populate_catalog(self):
        info = self.controller.data.supported_types()
        rows = list(info.items())
        self.catalog.setRowCount(len(rows))
        for row_idx, (key, item) in enumerate(rows):
            self.catalog.setItem(row_idx, 0, QTableWidgetItem(key))
            self.catalog.setItem(row_idx, 1, QTableWidgetItem(item.get("label", key)))
            self.catalog.setItem(row_idx, 2, QTableWidgetItem(item.get("default_software", "")))
            self.catalog.setItem(row_idx, 3, QTableWidgetItem(str(item.get("step_count", ""))))
        if rows:
            self.catalog.selectRow(0)

    def _sync_catalog_selection(self):
        rows = self.catalog.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        key = self.catalog.item(row, 0).text()
        self.data_type.setCurrentText(key)
        info = self.controller.data.supported_types().get(key, {})
        summary = [
            f"<h3>{key} · {info.get('label', key)}</h3>",
            f"<p><strong>Software:</strong> {info.get('default_software', 'TBD')}</p>",
            f"<p>{info.get('story', '')}</p>",
            f"<p><strong>Why this template:</strong> {info.get('why_template', '')}</p>",
            "<ul>",
        ]
        for item in info.get("qc_checks", []):
            summary.append(f"<li>{item}</li>")
        summary.append("</ul>")
        self.template_story.setHtml("".join(summary))

    def _load_template(self):
        self.controller.load_template(self.data_type.currentText(), self._metadata())

    def _load_current_flow(self, flow=None):
        flow = flow or self.controller.current_flow
        self.data_type.setCurrentText(flow.data_type)
        self.project_name.setText(flow.project_name)
        self.client.setText(flow.client)
        self.vessel.setText(flow.vessel)
        self.area.setText(flow.area)
        self.software.setText(flow.software)
        self.software_version.setText(flow.software_version)
        self.date.setText(flow.date)
        self.line_count.setValue(flow.line_count)
        self.notes.setText(flow.notes)

