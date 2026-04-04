"""Application state and orchestration for the PySide6 desktop shell."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal

from core import RevisionTracker

from desktop.services.data_service import DraftDataService
from desktop.services.export_service import DraftExportService
from desktop.services.report_service import DraftReportService


class DraftController(QObject):
    """Keep the current flow and a small in-memory revision trail."""

    flow_changed = Signal(object)
    activity_logged = Signal(str, str)

    def __init__(self):
        super().__init__()
        self.data = DraftDataService()
        self.report = DraftReportService()
        self.exporter = DraftExportService()
        self.revision_tracker = RevisionTracker()
        self.metadata: dict[str, str | int] = {}
        self.output_dir = str(Path.home() / "ProcessingReportDraft_Output")
        self.current_flow = self.data.template_flow("SBP", self.metadata)
        self.last_preview = self.report.build_preview_bundle(self.current_flow)
        self._snapshot("Loaded default SBP template")

    def _snapshot(self, reason: str) -> None:
        self.revision_tracker.save_revision(
            self.current_flow,
            author="desktop",
            changes=reason,
        )

    def _emit(self, reason: str, level: str = "info") -> None:
        self.last_preview = self.report.build_preview_bundle(self.current_flow)
        self._snapshot(reason)
        self.activity_logged.emit(reason, level)
        self.flow_changed.emit(self.current_flow)

    def set_output_dir(self, path: str) -> None:
        self.output_dir = path
        self.activity_logged.emit(f"Output folder set to {path}", "info")

    def load_template(self, data_type: str, metadata: dict | None = None) -> None:
        if metadata:
            self.metadata.update(metadata)
        self.current_flow = self.data.template_flow(data_type, self.metadata)
        self._emit(f"Loaded {self.current_flow.data_type} template", "success")

    def parse_log(self, log_text: str, metadata: dict | None = None) -> None:
        if metadata:
            self.metadata.update(metadata)
        self.current_flow = self.data.parse_flow(log_text, self.metadata)
        self._emit(f"Parsed processing log ({self.current_flow.step_count} steps)", "success")

    def update_metadata(self, metadata: dict) -> None:
        self.metadata.update({k: v for k, v in metadata.items() if v not in (None, "")})
        self.current_flow = self.data.apply_metadata(self.current_flow, self.metadata)
        self._emit("Updated report metadata", "info")

    def replace_flow(self, flow, reason: str = "Updated flow") -> None:
        self.current_flow = self.data.clone_flow(flow)
        self._emit(reason, "info")

    def add_step(self, **payload) -> None:
        self.current_flow = self.data.add_step(self.current_flow, **payload)
        self._emit(f"Added step: {payload.get('name', 'Custom step')}", "success")

    def update_step(self, order: int, **fields) -> None:
        self.current_flow = self.data.update_step(self.current_flow, order, **fields)
        self._emit(f"Updated step #{order}", "info")

    def remove_step(self, order: int) -> None:
        self.current_flow = self.data.remove_step(self.current_flow, order)
        self._emit(f"Removed step #{order}", "warning")

    def reorder_steps(self, new_order: list[int]) -> None:
        self.current_flow = self.data.reorder_steps(self.current_flow, new_order)
        self._emit("Reordered processing steps", "info")

    def refresh(self) -> None:
        self.last_preview = self.report.build_preview_bundle(self.current_flow)
        self.flow_changed.emit(self.current_flow)

    def export_flow(self, output_path: str, fmt: str) -> str:
        saved = self.exporter.export_flow(self.current_flow, output_path, fmt)
        self.activity_logged.emit(f"Exported {Path(saved).name}", "success")
        return saved

    def export_all_templates(self, output_dir: str) -> list[str]:
        saved = self.exporter.export_all_templates(output_dir, self.metadata)
        self.activity_logged.emit(f"Generated {len(saved)} template report(s)", "success")
        return saved

