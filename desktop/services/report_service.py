"""Preview/report helpers for the ProcessingReportDraft desktop shell."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from core import (
    build_flow_context,
    compare_flows,
    generate_flow_from_template,
    generate_html_report,
    generate_json_export,
    generate_text_report,
    get_flow_statistics,
    validate_flow_parameters,
)


class DraftReportService:
    """Build preview bundles and lightweight report summaries."""

    TEMPLATE_METADATA_FIELDS = (
        "project_name",
        "client",
        "vessel",
        "area",
        "date",
        "software",
        "software_version",
        "line_count",
        "notes",
    )

    def _template_metadata(self, flow) -> dict[str, Any]:
        metadata: dict[str, Any] = {}
        for field in self.TEMPLATE_METADATA_FIELDS:
            value = getattr(flow, field, "")
            if value not in ("", None):
                metadata[field] = value
        return metadata

    def build_preview_bundle(self, flow) -> dict[str, Any]:
        cloned = copy.deepcopy(flow)
        context = build_flow_context(cloned)
        return {
            "context": context,
            "html": generate_html_report(cloned),
            "text": generate_text_report(cloned),
            "json": generate_json_export(cloned),
            "validation": validate_flow_parameters(cloned),
            "statistics": get_flow_statistics(cloned),
        }

    def build_summary_cards(self, flow) -> list[dict[str, str]]:
        context = build_flow_context(copy.deepcopy(flow))
        stats = context["statistics"]
        validation = context["validation"]
        return [
            {
                "label": "Draft readiness",
                "value": context["readiness"]["label"],
                "detail": context["readiness"]["detail"],
            },
            {
                "label": "Workflow steps",
                "value": str(stats["step_count"]),
                "detail": f"{stats['stage_count']} stages · {stats['total_parameters']} parameters",
            },
            {
                "label": "Validation",
                "value": f"{validation['score']}%",
                "detail": f"{validation['valid']} valid · {validation['invalid']} invalid · {validation['unknown']} unknown",
            },
            {
                "label": "Placeholders",
                "value": str(stats["tbd_parameters"]),
                "detail": "Replace TBD values before final issue.",
            },
        ]

    def build_stage_rows(self, flow) -> list[dict[str, str]]:
        context = build_flow_context(copy.deepcopy(flow))
        rows: list[dict[str, str]] = []
        for group in context["stage_groups"]:
            rows.append(
                {
                    "stage": group["stage"],
                    "steps": str(group["step_count"]),
                    "summary": group["summary"],
                }
            )
        return rows

    def build_template_comparison(self, flow) -> dict[str, Any]:
        baseline = generate_flow_from_template(flow.data_type or "SBP")
        for field, value in self._template_metadata(flow).items():
            setattr(baseline, field, value)
        diff = compare_flows(copy.deepcopy(baseline), copy.deepcopy(flow))

        step_changes = {
            "added": len(diff.added_steps),
            "removed": len(diff.removed_steps),
            "modified": len(diff.modified_steps),
        }
        metadata_fields = list(diff.metadata_changes.keys())
        total_changes = sum(step_changes.values()) + len(metadata_fields)

        highlights: list[str] = []
        for step in diff.added_steps[:3]:
            highlights.append(f"Added step: {step.name}")
        for step in diff.removed_steps[:3]:
            highlights.append(f"Removed step: {step.name}")
        for step in diff.modified_steps[:3]:
            highlights.append(f"Modified step: {step['name']}")
        for field in metadata_fields[:3]:
            highlights.append(f"Metadata changed: {field.replace('_', ' ')}")

        if total_changes == 0:
            status = "Matches template baseline"
            summary = f"No differences from the {baseline.data_type} template baseline."
            highlights = ["No template differences detected."]
        else:
            status = "Template differences detected"
            parts = []
            if step_changes["added"]:
                parts.append(f"{step_changes['added']} step(s) added")
            if step_changes["removed"]:
                parts.append(f"{step_changes['removed']} step(s) removed")
            if step_changes["modified"]:
                parts.append(f"{step_changes['modified']} step(s) modified")
            if metadata_fields:
                parts.append(f"{len(metadata_fields)} metadata field(s) changed")
            summary = f"{', '.join(parts)} relative to the {baseline.data_type} template."

        return {
            "label": "Template comparison",
            "baseline": f"{baseline.data_type} template",
            "status": status,
            "summary": summary,
            "step_changes": step_changes,
            "metadata_changes": len(metadata_fields),
            "metadata_fields": metadata_fields,
            "highlights": highlights,
        }

    def _build_signoff_block(self, packet_context: dict[str, Any]) -> dict[str, Any]:
        readiness = packet_context["readiness"]
        current_state = packet_context["current_state"]
        blocking_items = packet_context["blocking_items"]
        last_export = packet_context["last_export"]

        can_sign_off = (
            readiness.get("tone") == "ok"
            and not blocking_items
            and current_state["validation_score"] >= 80
            and bool(last_export.get("available"))
        )
        needs_review = not can_sign_off

        checklist: list[str] = []
        if blocking_items:
            checklist.append("Review and clear the blocking items before handoff.")
        else:
            checklist.append("Confirm there are no open blockers in the draft.")

        if current_state["validation_score"] < 80:
            checklist.append(f"Raise validation from {current_state['validation_score']}% before sign-off.")
        else:
            checklist.append("Confirm the validation score is acceptable for reviewer handoff.")

        if last_export.get("available"):
            checklist.append(f"Verify the last export target is {last_export.get('target') or 'TBD'}.")
        else:
            checklist.append("Record the latest export target and path before signing off.")

        if can_sign_off:
            checklist.append("Proceed with reviewer sign-off and archive the packet.")
        else:
            checklist.append("Refresh the packet after fixes and re-check readiness.")

        return {
            "can_sign_off": can_sign_off,
            "needs_review": needs_review,
            "checklist": checklist,
        }

    def _build_handoff_summary(
        self,
        *,
        context: dict[str, Any],
        comparison: dict[str, Any],
        blocking_items: list[str],
        recommended_actions: list[str],
        signoff: dict[str, Any],
        validation_score: int,
        last_export: dict[str, Any],
    ) -> dict[str, Any]:
        attention_parts: list[str] = []
        if blocking_items:
            attention_parts.append(f"{len(blocking_items)} open item(s) remain")
        if validation_score < 80:
            attention_parts.append(f"validation is at {validation_score}%")
        if not last_export.get("available"):
            attention_parts.append("no export target has been recorded")

        if attention_parts:
            attention_summary = "; ".join(attention_parts) + "."
        else:
            attention_summary = "No blocking items remain; the packet is ready for reviewer handoff."

        change_highlights = comparison.get("highlights", [])[:3]
        if not change_highlights:
            change_highlights = ["No template-specific highlights were needed."]

        attention_items = blocking_items[:3] if blocking_items else signoff["checklist"][:2]
        review_check = signoff["checklist"][0] if signoff["checklist"] else "Refresh the packet after edits."
        next_step = recommended_actions[0] if recommended_actions else "Refresh the packet after edits."

        return {
            "label": "Author / reviewer handoff",
            "story": context["executive_summary"],
            "strategy": context["processing_strategy"],
            "change_summary": comparison["summary"],
            "change_highlights": change_highlights,
            "attention_summary": attention_summary,
            "attention_items": attention_items,
            "status": "Reviewer handoff ready" if signoff["can_sign_off"] else "Author revision required",
            "next_step": next_step,
            "review_check": review_check,
        }

    def build_operator_packet(
        self,
        flow,
        preview_bundle: dict[str, Any] | None = None,
        *,
        last_export_target: str = "",
        last_export_path: str = "",
    ) -> dict[str, Any]:
        bundle = preview_bundle or self.build_preview_bundle(flow)
        context = bundle["context"]
        validation = bundle["validation"]
        stats = bundle["statistics"]

        blocking_items: list[str] = []
        seen: set[str] = set()

        def add_block(item: str) -> None:
            item = item.strip()
            if item and item not in seen:
                seen.add(item)
                blocking_items.append(item)

        for item in context.get("open_items", []):
            add_block(str(item))

        for issue in validation.get("issues", []):
            if issue.get("severity") == "error":
                add_block(
                    f"Resolve {issue.get('step', 'Step')} - {issue.get('parameter', 'Parameter')}: {issue.get('expected', 'expected value')}."
                )

        recommended_actions: list[str] = []
        if blocking_items:
            if validation.get("invalid", 0):
                recommended_actions.append("Fix the invalid parameters flagged in the validation table first.")
            if stats.get("tbd_parameters", 0):
                recommended_actions.append("Replace the remaining TBD values with project-specific values.")
            if stats.get("missing_metadata"):
                recommended_actions.append("Confirm the missing project metadata before final issue.")
            recommended_actions.append("Refresh the preview after each fix and check whether the readiness label improves.")
        else:
            recommended_actions.append("Use this draft as the current export baseline.")
            recommended_actions.append("Confirm the output folder and filename before writing files.")
            recommended_actions.append("Save the packet as JSON or Markdown for operator handoff if review needs to continue.")

        export_state = {
            "target": last_export_target.strip(),
            "path": last_export_path.strip(),
            "available": bool(last_export_target.strip() or last_export_path.strip()),
        }
        template_comparison = self.build_template_comparison(flow)
        signoff = self._build_signoff_block(
            {
                "readiness": context["readiness"],
                "current_state": {
                    "validation_score": validation["score"],
                },
                "blocking_items": blocking_items,
                "last_export": export_state,
            }
        )
        handoff_summary = self._build_handoff_summary(
            context=context,
            comparison=template_comparison,
            blocking_items=blocking_items,
            recommended_actions=recommended_actions,
            signoff=signoff,
            validation_score=validation["score"],
            last_export=export_state,
        )

        return {
            "title": "ProcessingReportDraft operator packet",
            "project_name": flow.project_name or "TBD",
            "client": flow.client or "TBD",
            "data_type": flow.data_type or "TBD",
            "readiness": context["readiness"],
            "current_state": {
                "step_count": stats["step_count"],
                "stage_count": stats["stage_count"],
                "validation_score": validation["score"],
                "tbd_parameters": stats["tbd_parameters"],
                "open_items_count": len(context.get("open_items", [])),
                "summary": context["executive_summary"],
            },
            "template_comparison": template_comparison,
            "blocking_items": blocking_items,
            "recommended_next_actions": recommended_actions,
            "last_export": export_state,
            "sign_off": signoff,
            "handoff_summary": handoff_summary,
            "summary_cards": self.build_summary_cards(flow),
            "stage_rows": self.build_stage_rows(flow),
        }
