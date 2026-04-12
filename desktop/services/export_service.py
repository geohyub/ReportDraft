"""Export helpers for ProcessingReportDraft desktop."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import json

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

    def default_packet_filename(self, flow, fmt: str) -> str:
        project = (flow.project_name or "ProcessingReport").strip().replace(" ", "_")
        data_type = (flow.data_type or "SBP").upper()
        ext_map = {
            "json": ".json",
            "markdown": ".md",
            "md": ".md",
            "text": ".txt",
            "txt": ".txt",
        }
        return f"{project}_{data_type}_OperatorPacket{ext_map.get(fmt.lower(), '.json')}"

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

    def render_operator_packet_json(self, packet: dict[str, Any]) -> str:
        return json.dumps(packet, indent=2, ensure_ascii=False)

    def render_operator_packet_markdown(self, packet: dict[str, Any]) -> str:
        handoff = packet["handoff_summary"]
        readiness = packet["readiness"]
        current = packet["current_state"]
        comparison = packet["template_comparison"]
        signoff = packet["sign_off"]
        lines = [
            f"# {packet['title']}",
            "",
            f"**Project:** {packet['project_name']}  ",
            f"**Client:** {packet['client']}  ",
            f"**Data type:** {packet['data_type']}",
            "",
            "## Author / reviewer handoff",
            f"- Story: {handoff['story']}",
            f"- Strategy: {handoff['strategy']}",
            f"- Change summary: {handoff['change_summary']}",
            f"- Attention summary: {handoff['attention_summary']}",
            f"- Status: {handoff['status']}",
            f"- Next step: {handoff['next_step']}",
            f"- Review check: {handoff['review_check']}",
        ]
        if handoff["change_highlights"]:
            lines.append("- Change highlights:")
            lines.extend(f"  - {item}" for item in handoff["change_highlights"])
        if handoff["attention_items"]:
            lines.append("- Attention items:")
            lines.extend(f"  - {item}" for item in handoff["attention_items"])
        lines.extend([
            "",
            "## Readiness",
            f"- {readiness['label']}",
            f"- {readiness['detail']}",
            "",
            "## Current state",
            f"- Steps: {current['step_count']}",
            f"- Stages: {current['stage_count']}",
            f"- Validation score: {current['validation_score']}%",
            f"- Open items: {current['open_items_count']}",
            f"- Placeholder parameters: {current['tbd_parameters']}",
            "",
            "## Sign-off readiness",
            f"- Can sign off: {'Yes' if signoff['can_sign_off'] else 'No'}",
            f"- Needs review: {'Yes' if signoff['needs_review'] else 'No'}",
            "- Checklist:",
        ]
        lines.extend(f"  - {item}" for item in signoff["checklist"])
        lines.extend([
            "",
            "## Template comparison",
            f"- Baseline: {comparison['baseline']}",
            f"- Status: {comparison['status']}",
            f"- Summary: {comparison['summary']}",
            f"- Step changes: +{comparison['step_changes']['added']} · -{comparison['step_changes']['removed']} · ~{comparison['step_changes']['modified']}",
            f"- Metadata changes: {comparison['metadata_changes']}",
        ])
        if comparison["highlights"]:
            lines.extend(f"- {item}" for item in comparison["highlights"])
        lines.extend([
            "",
            "## Blocking items",
        ])
        if packet["blocking_items"]:
            lines.extend(f"- {item}" for item in packet["blocking_items"])
        else:
            lines.append("- No blocking items detected.")
        lines.extend([
            "",
            "## Recommended next actions",
        ])
        lines.extend(f"1. {action}" for action in packet["recommended_next_actions"])
        lines.extend([
            "",
            "## Last export",
        ])
        if packet["last_export"]["available"]:
            lines.append(f"- Target: {packet['last_export']['target'] or 'TBD'}")
            lines.append(f"- Path: {packet['last_export']['path'] or 'TBD'}")
        else:
            lines.append("- No export recorded yet.")
        return "\n".join(lines).strip() + "\n"

    def render_operator_packet_text(self, packet: dict[str, Any]) -> str:
        comparison = packet["template_comparison"]
        signoff = packet["sign_off"]
        lines = [
            "=" * 70,
            f"  {packet['title']}",
            "=" * 70,
            f"  Project: {packet['project_name']}",
            f"  Client: {packet['client']}",
            f"  Data type: {packet['data_type']}",
            "",
            "  Author / reviewer handoff",
            "  -------------------------",
            f"  Story:         {packet['handoff_summary']['story']}",
            f"  Strategy:      {packet['handoff_summary']['strategy']}",
            f"  Change summary:{packet['handoff_summary']['change_summary']}",
            f"  Attention:     {packet['handoff_summary']['attention_summary']}",
            f"  Status:        {packet['handoff_summary']['status']}",
            f"  Next step:     {packet['handoff_summary']['next_step']}",
            f"  Review check:  {packet['handoff_summary']['review_check']}",
        ]
        if packet["handoff_summary"]["change_highlights"]:
            lines.append("  Change highlights")
            lines.extend(f"  - {item}" for item in packet["handoff_summary"]["change_highlights"])
        if packet["handoff_summary"]["attention_items"]:
            lines.append("  Attention items")
            lines.extend(f"  - {item}" for item in packet["handoff_summary"]["attention_items"])
        lines.extend([
            "",
            f"  Readiness: {packet['readiness']['label']}",
            f"  Detail:    {packet['readiness']['detail']}",
            "",
            "  Current state",
            "  ------------",
            f"  Steps:     {packet['current_state']['step_count']}",
            f"  Stages:    {packet['current_state']['stage_count']}",
            f"  Validation:{packet['current_state']['validation_score']}%",
            f"  Open:      {packet['current_state']['open_items_count']}",
            f"  TBD:       {packet['current_state']['tbd_parameters']}",
            "",
            "  Sign-off readiness",
            "  ------------------",
            f"  Can sign off: {'Yes' if signoff['can_sign_off'] else 'No'}",
            f"  Needs review: {'Yes' if signoff['needs_review'] else 'No'}",
        ]
        lines.extend(f"  - {item}" for item in signoff["checklist"])
        lines.extend([
            "",
            "  Template comparison",
            "  -------------------",
            f"  Baseline: {comparison['baseline']}",
            f"  Status:   {comparison['status']}",
            f"  Summary:  {comparison['summary']}",
            f"  Steps:    +{comparison['step_changes']['added']} / -{comparison['step_changes']['removed']} / ~{comparison['step_changes']['modified']}",
            f"  Metadata: {comparison['metadata_changes']} field(s) changed",
        ])
        if comparison["highlights"]:
            lines.extend(f"  - {item}" for item in comparison["highlights"])
        lines.extend([
            "",
            "  Blocking items",
            "  --------------",
        ])
        if packet["blocking_items"]:
            lines.extend(f"  - {item}" for item in packet["blocking_items"])
        else:
            lines.append("  - No blocking items detected.")
        lines.extend([
            "",
            "  Recommended next actions",
            "  ------------------------",
        ])
        lines.extend(f"  {idx + 1}. {action}" for idx, action in enumerate(packet["recommended_next_actions"]))
        lines.extend([
            "",
            "  Last export",
            "  -----------",
        ])
        if packet["last_export"]["available"]:
            lines.append(f"  Target: {packet['last_export']['target'] or 'TBD'}")
            lines.append(f"  Path:   {packet['last_export']['path'] or 'TBD'}")
        else:
            lines.append("  No export recorded yet.")
        return "\n".join(lines) + "\n"

    def export_operator_packet(self, packet: dict[str, Any], output_path: str | Path, fmt: str) -> str:
        output_path = Path(output_path)
        fmt = fmt.lower()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if fmt == "json":
            output_path.write_text(self.render_operator_packet_json(packet), encoding="utf-8")
        elif fmt in {"markdown", "md"}:
            output_path.write_text(self.render_operator_packet_markdown(packet), encoding="utf-8")
        elif fmt in {"text", "txt"}:
            output_path.write_text(self.render_operator_packet_text(packet), encoding="utf-8")
        else:
            raise ValueError(f"Unsupported operator packet format: {fmt}")
        return str(output_path)

    def export_all_templates(self, output_dir: str | Path, metadata: dict[str, Any] | None = None) -> list[str]:
        metadata = metadata or {}
        from desktop.services.data_service import DraftDataService

        service = DraftDataService()
        flows = service.bulk_templates(metadata)
        return generate_bulk_docx(flows, str(output_dir))
