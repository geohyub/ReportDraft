"""Preview/report helpers for the ProcessingReportDraft desktop shell."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from core import (
    build_flow_context,
    generate_html_report,
    generate_json_export,
    generate_text_report,
    get_flow_statistics,
    validate_flow_parameters,
)


class DraftReportService:
    """Build preview bundles and lightweight report summaries."""

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

