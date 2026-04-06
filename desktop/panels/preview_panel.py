"""Preview panel for HTML / text / JSON / validation views."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QTextBrowser,
    QPlainTextEdit,
    QPushButton,
)

from geoview_pyside6.constants import Dark
from geoview_pyside6.widgets import KPICard, GVTableView


class PreviewPanel(QWidget):
    panel_title = "Preview"

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        top = QHBoxLayout()
        self.cards = [
            KPICard("shield-check", "--", "Readiness", accent=Dark.GREEN),
            KPICard("list-ordered", "--", "Steps", accent=Dark.BLUE),
            KPICard("check-circle", "--", "Validation", accent=Dark.CYAN),
            KPICard("alert-circle", "--", "Placeholders", accent=Dark.ORANGE),
        ]
        for card in self.cards:
            top.addWidget(card)
        root.addLayout(top)

        self.refresh_btn = QPushButton("Refresh preview")
        self.refresh_btn.clicked.connect(self._refresh)
        root.addWidget(self.refresh_btn)

        self.tabs = QTabWidget()
        self.overview = QTextBrowser()
        self.html_view = QTextBrowser()
        self.text_view = QPlainTextEdit()
        self.text_view.setReadOnly(True)
        self.json_view = QPlainTextEdit()
        self.json_view.setReadOnly(True)
        self.validation_table = GVTableView()
        self.validation_table.show_empty_state(
            "No validation issues",
            icon_name="check-circle",
            subtitle="Run preview to see validation results",
        )
        self.stats_table = GVTableView()
        self.stats_table.show_empty_state(
            "No statistics available",
            icon_name="bar-chart-2",
            subtitle="Load a template to see statistics",
        )

        self.tabs.addTab(self.overview, "Overview")
        self.tabs.addTab(self.html_view, "HTML")
        self.tabs.addTab(self.text_view, "Text")
        self.tabs.addTab(self.json_view, "JSON")
        self.tabs.addTab(self.validation_table, "Validation")
        self.tabs.addTab(self.stats_table, "Statistics")
        root.addWidget(self.tabs)

        self.controller.flow_changed.connect(self.refresh_flow)
        self._refresh()

    def _refresh(self):
        self.refresh_flow(self.controller.current_flow)

    def refresh_flow(self, flow):
        bundle = self.controller.report.build_preview_bundle(flow)
        context = bundle["context"]
        validation = bundle["validation"]
        stats = bundle["statistics"]

        self.cards[0].set_value(context["readiness"]["label"])
        self.cards[0].set_label(context["readiness"]["detail"])
        self.cards[1].set_value(str(stats["step_count"]))
        self.cards[1].set_label(f"{stats['stage_count']} stage(s)")
        self.cards[2].set_value(f"{validation['score']}%")
        self.cards[2].set_label(f"{validation['valid']} valid / {validation['invalid']} invalid")
        self.cards[3].set_value(str(stats["tbd_parameters"]))
        self.cards[3].set_label("Open placeholders")

        overview_html = [
            f"<h2>{context['headline']}</h2>",
            "<p><strong>Project:</strong> "
            f"{flow.project_name or 'TBD'}"
            " · <strong>Client:</strong> "
            f"{flow.client or 'TBD'}"
            " · <strong>Vessel:</strong> "
            f"{flow.vessel or 'TBD'}"
            "</p>",
            f"<p>{context['summary']}</p>",
            f"<h3>Processing strategy</h3><p>{context['processing_strategy']}</p>",
            f"<h3>QC focus</h3><p>{context['qc_story']}</p>",
            "<h3>Open items</h3>",
            "<ul>",
        ]
        for item in context["open_items"] or ["No blocking placeholders detected."]:
            overview_html.append(f"<li>{item}</li>")
        overview_html.append("</ul>")
        self.overview.setHtml("".join(overview_html))
        self.html_view.setHtml(bundle["html"])
        self.text_view.setPlainText(bundle["text"])
        self.json_view.setPlainText(bundle["json"])

        issues = validation.get("issues", [])
        if issues:
            self.validation_table.hide_empty_state()
            val_data = [
                [str(issue.get(k, "")) for k in ("step", "parameter", "value", "expected", "severity")]
                for issue in issues
            ]
            self.validation_table.set_data(
                ["Step", "Parameter", "Value", "Expected", "Severity"], val_data,
            )
        else:
            self.validation_table.show_empty_state(
                "No validation issues", icon_name="check-circle",
            )

        stats_items = [
            ("step_count", stats["step_count"]),
            ("stage_count", stats["stage_count"]),
            ("total_parameters", stats["total_parameters"]),
            ("tbd_parameters", stats["tbd_parameters"]),
            ("completeness_score", stats["completeness_score"]),
            ("draft_readiness", stats["draft_readiness"]),
            ("has_metadata", stats["has_metadata"]),
        ]
        self.stats_table.hide_empty_state()
        self.stats_table.set_data(
            ["Key", "Value"],
            [[str(k), str(v)] for k, v in stats_items],
        )
