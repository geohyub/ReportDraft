"""Data and flow helpers for the ProcessingReportDraft desktop shell."""

from __future__ import annotations

import copy
import json
from dataclasses import asdict
from typing import Any

from core import (
    ProcessingFlow,
    ProcessingStep,
    add_custom_step,
    build_flow_context,
    enrich_flow,
    generate_all_templates,
    generate_flow_from_template,
    get_supported_types,
    parse_processing_log,
    remove_step,
    reorder_steps,
    update_step,
)


class DraftDataService:
    """Thin wrapper around core.py so the desktop shell can stay lean."""

    def supported_types(self) -> dict[str, dict[str, Any]]:
        return get_supported_types()

    def template_flow(self, data_type: str, metadata: dict[str, Any] | None = None) -> ProcessingFlow:
        flow = generate_flow_from_template(data_type)
        return self.apply_metadata(flow, metadata)

    def parse_flow(self, log_text: str, metadata: dict[str, Any] | None = None) -> ProcessingFlow:
        flow = parse_processing_log(log_text)
        return self.apply_metadata(flow, metadata)

    def bulk_templates(self, metadata: dict[str, Any] | None = None) -> dict[str, ProcessingFlow]:
        metadata = metadata or {}
        flows = generate_all_templates(
            project_name=metadata.get("project_name", ""),
            client=metadata.get("client", ""),
            vessel=metadata.get("vessel", ""),
            area=metadata.get("area", ""),
        )
        for flow in flows.values():
            flow.software = metadata.get("software", flow.software)
            flow.software_version = metadata.get("software_version", flow.software_version)
            flow.date = metadata.get("date", flow.date)
            flow.line_count = int(metadata.get("line_count", flow.line_count) or 0)
            flow.notes = metadata.get("notes", flow.notes)
        return {key: enrich_flow(flow) for key, flow in flows.items()}

    def build_context(self, flow: ProcessingFlow) -> dict[str, Any]:
        return build_flow_context(copy.deepcopy(flow))

    def sample_log_text(self, flow: ProcessingFlow) -> str:
        flow = enrich_flow(copy.deepcopy(flow))
        lines = [
            f"Project: {flow.project_name or 'Demo Project'}",
            f"Client: {flow.client or 'GeoView'}",
            f"Data type: {flow.data_type}",
            f"Vessel: {flow.vessel or 'Survey Vessel'}",
            f"Area: {flow.area or 'Survey Area'}",
            f"Software: {flow.software} {flow.software_version}".strip(),
            "",
        ]
        for step in flow.steps:
            lines.append(f"{step.order}. {step.name} - {step.description or 'Processing step'}")
            for key, value in step.parameters.items():
                lines.append(f"   {key}: {value}")
            if step.rationale:
                lines.append(f"   Why: {step.rationale}")
            if step.qc_focus:
                lines.append(f"   QC focus: {step.qc_focus}")
            if step.expected_output:
                lines.append(f"   Expected output: {step.expected_output}")
            lines.append("")
        return "\n".join(lines).strip() + "\n"

    def apply_metadata(self, flow: ProcessingFlow, metadata: dict[str, Any] | None = None) -> ProcessingFlow:
        metadata = metadata or {}
        flow.project_name = metadata.get("project_name", flow.project_name)
        flow.client = metadata.get("client", flow.client)
        flow.vessel = metadata.get("vessel", flow.vessel)
        flow.area = metadata.get("area", flow.area)
        flow.date = metadata.get("date", flow.date)
        flow.software = metadata.get("software", flow.software)
        flow.software_version = metadata.get("software_version", flow.software_version)
        flow.notes = metadata.get("notes", flow.notes)
        flow.line_count = int(metadata.get("line_count", flow.line_count) or 0)
        return enrich_flow(flow)

    def clone_flow(self, flow: ProcessingFlow) -> ProcessingFlow:
        return enrich_flow(copy.deepcopy(flow))

    def add_step(
        self,
        flow: ProcessingFlow,
        *,
        name: str,
        description: str = "",
        parameters: dict[str, Any] | None = None,
        position: int | None = None,
        stage: str = "",
        rationale: str = "",
        qc_focus: str = "",
        expected_output: str = "",
    ) -> ProcessingFlow:
        updated = copy.deepcopy(flow)
        add_custom_step(
            updated,
            name=name,
            description=description,
            parameters=parameters or {},
            position=position,
            stage=stage,
            rationale=rationale,
            qc_focus=qc_focus,
            expected_output=expected_output,
        )
        return enrich_flow(updated)

    def remove_step(self, flow: ProcessingFlow, order: int) -> ProcessingFlow:
        updated = copy.deepcopy(flow)
        remove_step(updated, order)
        return enrich_flow(updated)

    def reorder_steps(self, flow: ProcessingFlow, new_order: list[int]) -> ProcessingFlow:
        updated = copy.deepcopy(flow)
        reorder_steps(updated, new_order)
        return enrich_flow(updated)

    def update_step(self, flow: ProcessingFlow, order: int, **fields) -> ProcessingFlow:
        updated = copy.deepcopy(flow)
        update_step(updated, order, **fields)
        return enrich_flow(updated)

