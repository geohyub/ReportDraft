"""Dashboard panel for ProcessingReportDraft."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTextBrowser,
    QListWidget,
    QListWidgetItem,
    QFrame,
    QLabel,
    QGroupBox,
    QSizePolicy,
)

from geoview_pyside6.constants import Dark
from geoview_pyside6.widgets import KPICard, GVTableView


class DashboardPanel(QWidget):
    panel_title = "Overview"

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        hero = QFrame()
        hero.setObjectName("heroCard")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(16, 14, 16, 14)
        hero_layout.setSpacing(8)

        self.title_label = QLabel("ProcessingReportDraft")
        self.title_label.setObjectName("heroTitle")
        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        self.summary_label.setObjectName("heroSummary")

        hero_layout.addWidget(self.title_label)
        hero_layout.addWidget(self.summary_label)
        root.addWidget(hero)

        cards = QHBoxLayout()
        cards.setSpacing(10)
        self.cards = [
            KPICard("database", "--", "Data type", accent=Dark.BLUE),
            KPICard("list-ordered", "--", "Workflow steps", accent=Dark.GREEN),
            KPICard("shield-check", "--", "Validation", accent=Dark.CYAN),
            KPICard("alert-circle", "--", "Placeholders", accent=Dark.ORANGE),
        ]
        for card in self.cards:
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            cards.addWidget(card)
        root.addLayout(cards)

        action_row = QHBoxLayout()
        self.apply_template_btn = QPushButton("Use Template")
        self.parse_log_btn = QPushButton("Parse Log")
        self.preview_btn = QPushButton("Open Preview")
        self.export_btn = QPushButton("Open Export")
        for btn in (self.apply_template_btn, self.parse_log_btn, self.preview_btn, self.export_btn):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            action_row.addWidget(btn)
        root.addLayout(action_row)

        body = QHBoxLayout()
        body.setSpacing(12)

        left_box = QGroupBox("Workflow Story")
        left_layout = QVBoxLayout(left_box)
        self.story = QTextBrowser()
        self.story.setOpenExternalLinks(False)
        left_layout.addWidget(self.story)
        body.addWidget(left_box, 2)

        right_box = QGroupBox("Stage Overview")
        right_layout = QVBoxLayout(right_box)
        self.stage_table = GVTableView()
        self.stage_table.show_empty_state(
            "No stages loaded",
            icon_name="layers",
            subtitle="Load a template to see workflow stages",
        )
        right_layout.addWidget(self.stage_table)

        self.activity_list = QListWidget()
        self.activity_list.setMinimumHeight(160)
        right_layout.addWidget(self.activity_list)
        body.addWidget(right_box, 2)

        root.addLayout(body)

        self.apply_template_btn.clicked.connect(lambda: self.controller.load_template("SBP"))
        self.parse_log_btn.clicked.connect(self._load_sample_log)
        self.preview_btn.clicked.connect(self.controller.refresh)
        self.export_btn.clicked.connect(self._open_export_hint)
        self.controller.flow_changed.connect(self.refresh_flow)
        self.controller.activity_logged.connect(self._append_activity)

        self.refresh_flow(self.controller.current_flow)
        self._append_activity("Default SBP template is ready.", "info")

    def _load_sample_log(self):
        sample = self.controller.data.sample_log_text(self.controller.current_flow)
        self.controller.parse_log(sample)

    def _open_export_hint(self):
        self._append_activity("Switch to Export to write DOCX, Excel, HTML, JSON, or Text.", "info")

    def _append_activity(self, text: str, level: str):
        prefix = {
            "success": "✓",
            "warning": "!",
            "error": "×",
            "info": "•",
        }.get(level, "•")
        self.activity_list.insertItem(0, QListWidgetItem(f"{prefix} {text}"))
        while self.activity_list.count() > 8:
            self.activity_list.takeItem(self.activity_list.count() - 1)

    def refresh_flow(self, flow):
        context = self.controller.report.build_preview_bundle(flow)["context"]
        stats = context["statistics"]
        validation = context["validation"]

        self.cards[0].set_value(context["label"])
        self.cards[0].set_label(context["processing_strategy"])
        self.cards[1].set_value(str(stats["step_count"]))
        self.cards[1].set_label(f"{stats['stage_count']} stage(s)")
        self.cards[2].set_value(f"{validation['score']}%")
        self.cards[2].set_label(f"{validation['valid']} valid / {validation['invalid']} invalid")
        self.cards[3].set_value(str(stats["tbd_parameters"]))
        self.cards[3].set_label("Open placeholders")

        self.summary_label.setText(context["executive_summary"])
        self.story.setHtml(
            "<h3>Why this template matters</h3>"
            f"<p>{context['why_template']}</p>"
            "<h3>QC focus</h3>"
            f"<p>{context['qc_story']}</p>"
            "<h3>Open items</h3>"
            f"<p>{context['open_story']}</p>"
        )

        rows = context["stage_groups"]
        if rows:
            self.stage_table.hide_empty_state()
            table_data = [
                [row["stage"], str(row["step_count"]), row["summary"]]
                for row in rows
            ]
            self.stage_table.set_data(["Stage", "Steps", "Summary"], table_data)
        else:
            self.stage_table.show_empty_state("No stages loaded", icon_name="layers")

