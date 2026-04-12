import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from desktop.services.data_service import DraftDataService
from desktop.services.export_service import DraftExportService
from desktop.services.report_service import DraftReportService


def _sample_flow():
    data = DraftDataService()
    return data.template_flow(
        "SBP",
        {
            "project_name": "Packet Project",
            "client": "GeoView",
            "vessel": "Vessel A",
            "area": "Test Area",
            "line_count": 11,
        },
    )


def _sample_flow_with_template_changes():
    data = DraftDataService()
    flow = _sample_flow()
    flow = data.add_step(
        flow,
        name="Custom QC Check",
        description="Review the draft against the template baseline",
        parameters={"reviewer": "Lead processor"},
        stage="Quality Control",
    )
    return data.update_step(
        flow,
        1,
        description="Updated input handling for the current project",
        parameters={"Input format": "SEG-Y Rev 2"},
    )


def test_operator_packet_includes_readiness_and_actions():
    flow = _sample_flow()
    report = DraftReportService()
    packet = report.build_operator_packet(
        flow,
        preview_bundle=report.build_preview_bundle(flow),
        last_export_target="docx",
        last_export_path="C:/tmp/packet.docx",
    )

    assert packet["project_name"] == "Packet Project"
    assert packet["readiness"]["label"]
    assert packet["current_state"]["validation_score"] >= 0
    assert packet["blocking_items"]
    assert packet["recommended_next_actions"]
    assert packet["last_export"]["available"] is True
    assert packet["last_export"]["path"] == "C:/tmp/packet.docx"


def test_operator_packet_includes_template_comparison_summary():
    flow = _sample_flow_with_template_changes()
    report = DraftReportService()
    packet = report.build_operator_packet(flow, preview_bundle=report.build_preview_bundle(flow))

    comparison = packet["template_comparison"]

    assert comparison["label"] == "Template comparison"
    assert comparison["baseline"] == "SBP template"
    assert comparison["step_changes"]["added"] == 1
    assert comparison["step_changes"]["modified"] >= 1
    assert comparison["summary"]
    assert "template" in comparison["summary"].lower()


def test_operator_packet_includes_handoff_summary():
    flow = _sample_flow_with_template_changes()
    report = DraftReportService()
    packet = report.build_operator_packet(flow, preview_bundle=report.build_preview_bundle(flow))

    handoff = packet["handoff_summary"]

    assert handoff["label"] == "Author / reviewer handoff"
    assert handoff["story"]
    assert handoff["strategy"]
    assert handoff["change_summary"]
    assert isinstance(handoff["change_highlights"], list)
    assert handoff["attention_summary"]
    assert isinstance(handoff["attention_items"], list)
    assert handoff["status"] in {"Reviewer handoff ready", "Author revision required"}
    assert handoff["next_step"]
    assert handoff["review_check"]


def test_operator_packet_includes_signoff_block():
    flow = _sample_flow()
    report = DraftReportService()
    packet = report.build_operator_packet(flow, preview_bundle=report.build_preview_bundle(flow))

    signoff = packet["sign_off"]

    assert "can_sign_off" in signoff
    assert "needs_review" in signoff
    assert isinstance(signoff["checklist"], list)
    assert signoff["checklist"]
    assert any("review" in item.lower() or "confirm" in item.lower() for item in signoff["checklist"])


def test_operator_packet_render_and_export(tmp_path):
    flow = _sample_flow()
    report = DraftReportService()
    exporter = DraftExportService()
    packet = report.build_operator_packet(flow, preview_bundle=report.build_preview_bundle(flow))

    json_path = tmp_path / exporter.default_packet_filename(flow, "json")
    md_path = tmp_path / exporter.default_packet_filename(flow, "markdown")
    txt_path = tmp_path / exporter.default_packet_filename(flow, "text")

    saved_json = exporter.export_operator_packet(packet, json_path, "json")
    saved_md = exporter.export_operator_packet(packet, md_path, "markdown")
    saved_txt = exporter.export_operator_packet(packet, txt_path, "text")

    assert os.path.exists(saved_json)
    assert os.path.exists(saved_md)
    assert os.path.exists(saved_txt)
    assert "operator packet" in exporter.render_operator_packet_markdown(packet).lower()
    assert "author / reviewer handoff" in exporter.render_operator_packet_markdown(packet).lower()
    assert "template comparison" in exporter.render_operator_packet_markdown(packet).lower()
    assert "sign-off" in exporter.render_operator_packet_markdown(packet).lower()
    assert "readiness" in exporter.render_operator_packet_text(packet).lower()
    assert "author / reviewer handoff" in exporter.render_operator_packet_text(packet).lower()
    assert "template comparison" in exporter.render_operator_packet_text(packet).lower()
    assert "sign-off" in exporter.render_operator_packet_text(packet).lower()
