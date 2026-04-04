"""Export helpers for ProcessingReportDraft desktop."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core import (
    generate_bulk_docx,
    generate_excel_report,
    generate_html_report,
    generate_json_export,
    generate_text_report,
)


class DraftExportService:
    """Write desktop-export artifacts without touching the Flask entry point."""

    def default_filename(self, flow, fmt: str) -> str:
        project = (flow.project_name or "ProcessingReport").strip().replace(" ", "_")
        data_type = (flow.data_type or "SBP").upper()
        ext_map = {
            "docx": ".docx",
            "excel": ".xlsx",
            "html": ".html",
            "json": ".json",
            "text": ".txt",
        }
        return f"{project}_{data_type}_Draft{ext_map.get(fmt, '.docx')}"

    def export_flow(self, flow, output_path: str | Path, fmt: str) -> str:
        output_path = Path(output_path)
        fmt = fmt.lower()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if fmt == "docx":
            from core import generate_docx_report

            generate_docx_report(flow, str(output_path))
        elif fmt == "excel":
            generate_excel_report(flow, str(output_path))
        elif fmt == "html":
            output_path.write_text(generate_html_report(flow), encoding="utf-8")
        elif fmt == "json":
            output_path.write_text(generate_json_export(flow), encoding="utf-8")
        elif fmt == "text":
            output_path.write_text(generate_text_report(flow), encoding="utf-8")
        else:
            raise ValueError(f"Unsupported export format: {fmt}")
        return str(output_path)

    def export_all_templates(self, output_dir: str | Path, metadata: dict[str, Any] | None = None) -> list[str]:
        metadata = metadata or {}
        from desktop.services.data_service import DraftDataService

        service = DraftDataService()
        flows = service.bulk_templates(metadata)
        return generate_bulk_docx(flows, str(output_dir))
