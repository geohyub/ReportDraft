"""ProcessingReportDraft - Flask Web GUI Application — v3.0."""
import io
import os
import sys
import json
import tempfile
import zipfile
from datetime import datetime
from dataclasses import asdict

from flask import Flask, render_template, request, jsonify, send_file

sys.path.insert(0, os.path.dirname(__file__))
from core import (
    parse_processing_log,
    generate_docx_report,
    generate_text_report,
    generate_flow_from_template,
    get_supported_types,
    ProcessingFlow,
    ProcessingStep,
    SUPPORTED_DATA_TYPES,
    add_custom_step,
    remove_step,
    reorder_steps,
    update_step,
    compare_flows,
    FlowDiff,
    RevisionTracker,
    _serialize_flow,
    validate_flow_parameters,
    get_flow_statistics,
    compare_flow_statistics,
    generate_excel_report,
    generate_json_export,
    generate_html_report,
    generate_all_templates,
    generate_bulk_docx,
    build_flow_context,
    enrich_flow,
)


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "geoview-processingreport-dev-2026")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max

_last_flow = {}
_revision_tracker = RevisionTracker()


def flow_to_dict(flow):
    """Convert ProcessingFlow to a JSON-serializable dict."""
    flow = enrich_flow(flow)
    context = build_flow_context(flow)
    return {
        "project_name": flow.project_name,
        "client": flow.client,
        "data_type": flow.data_type,
        "vessel": flow.vessel,
        "area": flow.area,
        "date": flow.date,
        "software": flow.software,
        "software_version": flow.software_version,
        "line_count": flow.line_count,
        "notes": flow.notes,
        "step_count": flow.step_count,
        "steps": [
            {
                "order": s.order,
                "name": s.name,
                "description": s.description,
                "parameters": s.parameters,
                "stage": s.stage,
                "rationale": s.rationale,
                "qc_focus": s.qc_focus,
                "expected_output": s.expected_output,
            }
            for s in flow.steps
        ],
        "statistics": context["statistics"],
        "validation": context["validation"],
        "context": context,
    }


def dict_to_flow(d):
    """Convert a dict back to a ProcessingFlow object."""
    flow = ProcessingFlow(
        project_name=d.get("project_name", ""),
        client=d.get("client", ""),
        data_type=d.get("data_type", "SBP"),
        vessel=d.get("vessel", ""),
        area=d.get("area", ""),
        date=d.get("date", ""),
        software=d.get("software", "RadExPro"),
        software_version=d.get("software_version", ""),
        line_count=d.get("line_count", 0),
        notes=d.get("notes", ""),
    )
    flow.steps = [
        ProcessingStep(
            order=s.get("order", i + 1),
            name=s.get("name", ""),
            description=s.get("description", ""),
            parameters=s.get("parameters", {}),
            stage=s.get("stage", ""),
            rationale=s.get("rationale", ""),
            qc_focus=s.get("qc_focus", ""),
            expected_output=s.get("expected_output", ""),
        )
        for i, s in enumerate(d.get("steps", []))
    ]
    return enrich_flow(flow)


@app.route("/")
def index():
    """Main page."""
    return render_template("index.html")


@app.route("/api/data_types", methods=["GET"])
def api_data_types():
    """Return supported data types."""
    try:
        types_info = get_supported_types()
        return jsonify({
            "ok": True,
            "supported": SUPPORTED_DATA_TYPES,
            "details": types_info,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/template", methods=["POST"])
def api_template():
    """Generate a processing flow from a template."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "JSON body required"}), 400

        data_type = data.get("data_type", "SBP").upper()
        flow = generate_flow_from_template(data_type)

        # Apply user-provided metadata
        flow.project_name = data.get("project_name", "")
        flow.client = data.get("client", "")
        flow.vessel = data.get("vessel", "")
        flow.area = data.get("area", "")
        flow.software = data.get("software", flow.software)
        flow.line_count = int(data.get("line_count", 0) or 0)

        # Store for export
        _last_flow["flow"] = flow

        return jsonify(flow_to_dict(flow))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/parse", methods=["POST"])
def api_parse():
    """Parse processing log text."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "JSON body required"}), 400

        log_text = data.get("log_text", "")
        if not log_text.strip():
            return jsonify({"error": "log_text is empty"}), 400

        flow = parse_processing_log(log_text)

        # Store for export
        _last_flow["flow"] = flow

        return jsonify(flow_to_dict(flow))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/download", methods=["POST"])
def api_download():
    """Generate and download a DOCX report."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "JSON body required"}), 400

        flow = dict_to_flow(data)

        # Generate DOCX in a temp file
        tmp = tempfile.NamedTemporaryFile(
            suffix=".docx", delete=False, prefix="report_"
        )
        tmp_path = tmp.name
        tmp.close()

        generate_docx_report(flow, tmp_path)

        # Build filename
        data_type = flow.data_type or "SBP"
        project = flow.project_name.replace(" ", "_") if flow.project_name else ""
        if project:
            filename = f"Processing_Report_{data_type}_{project}.docx"
        else:
            filename = f"Processing_Report_{data_type}.docx"

        return send_file(
            tmp_path,
            as_attachment=True,
            download_name=filename,
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/export_text", methods=["POST"])
def api_export_text():
    """Export the last flow as a text report."""
    try:
        data = request.get_json(silent=True)

        # If explicit flow data is provided, use it; otherwise use stored
        if data and "steps" in data:
            flow = dict_to_flow(data)
        elif "flow" in _last_flow:
            flow = _last_flow["flow"]
        else:
            return jsonify({"error": "표시할 처리 흐름이 없습니다."}), 400

        report = generate_text_report(flow)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        tmp = tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w", encoding="utf-8")
        tmp.write(report)
        tmp.close()

        return send_file(
            tmp.name,
            as_attachment=True,
            download_name=f"ProcessingReport_{timestamp}.txt",
            mimetype="text/plain",
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/step/add", methods=["POST"])
def api_add_step():
    """Add a custom step to the current flow."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "JSON body required"}), 400

        name = data.get("name", "")
        if not name:
            return jsonify({"error": "Step name is required"}), 400

        description = data.get("description", "")
        parameters = data.get("parameters", {})
        position = data.get("position", None)
        stage = data.get("stage", "")
        rationale = data.get("rationale", "")
        qc_focus = data.get("qc_focus", "")
        expected_output = data.get("expected_output", "")

        # Use provided flow data or stored flow
        if "flow" in data:
            flow = dict_to_flow(data["flow"])
        elif "flow" in _last_flow:
            flow = _last_flow["flow"]
        else:
            flow = ProcessingFlow()

        add_custom_step(
            flow,
            name,
            description,
            parameters,
            position,
            stage=stage,
            rationale=rationale,
            qc_focus=qc_focus,
            expected_output=expected_output,
        )
        _last_flow["flow"] = flow
        return jsonify(flow_to_dict(flow))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/step/remove", methods=["POST"])
def api_remove_step():
    """Remove a step from the current flow."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "JSON body required"}), 400

        order = data.get("order")
        if order is None:
            return jsonify({"error": "Step order number is required"}), 400

        if "flow" in data:
            flow = dict_to_flow(data["flow"])
        elif "flow" in _last_flow:
            flow = _last_flow["flow"]
        else:
            return jsonify({"error": "No flow available"}), 400

        remove_step(flow, int(order))
        _last_flow["flow"] = flow
        return jsonify(flow_to_dict(flow))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/step/reorder", methods=["POST"])
def api_reorder_steps():
    """Reorder steps in the current flow."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "JSON body required"}), 400

        new_order = data.get("new_order")
        if not new_order:
            return jsonify({"error": "new_order list is required"}), 400

        if "flow" in data:
            flow = dict_to_flow(data["flow"])
        elif "flow" in _last_flow:
            flow = _last_flow["flow"]
        else:
            return jsonify({"error": "No flow available"}), 400

        reorder_steps(flow, new_order)
        _last_flow["flow"] = flow
        return jsonify(flow_to_dict(flow))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/step/update", methods=["POST"])
def api_update_step():
    """Update a step's properties."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "JSON body required"}), 400

        order = data.get("order")
        if order is None:
            return jsonify({"error": "Step order number is required"}), 400

        if "flow" in data:
            flow = dict_to_flow(data["flow"])
        elif "flow" in _last_flow:
            flow = _last_flow["flow"]
        else:
            return jsonify({"error": "No flow available"}), 400

        update_step(
            flow,
            int(order),
            name=data.get("name"),
            description=data.get("description"),
            parameters=data.get("parameters"),
            stage=data.get("stage"),
            rationale=data.get("rationale"),
            qc_focus=data.get("qc_focus"),
            expected_output=data.get("expected_output"),
        )
        _last_flow["flow"] = flow
        return jsonify(flow_to_dict(flow))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/compare_flows", methods=["POST"])
def api_compare_flows():
    """Compare two flows."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "JSON body required"}), 400

        flow1_data = data.get("flow1")
        flow2_data = data.get("flow2")
        if not flow1_data or not flow2_data:
            return jsonify({"error": "Both flow1 and flow2 are required"}), 400

        flow1 = dict_to_flow(flow1_data)
        flow2 = dict_to_flow(flow2_data)
        diff = compare_flows(flow1, flow2)

        return jsonify({
            "added_steps": [
                {
                    "order": s.order,
                    "name": s.name,
                    "description": s.description,
                    "parameters": s.parameters,
                    "stage": s.stage,
                    "rationale": s.rationale,
                    "qc_focus": s.qc_focus,
                    "expected_output": s.expected_output,
                }
                for s in diff.added_steps
            ],
            "removed_steps": [
                {
                    "order": s.order,
                    "name": s.name,
                    "description": s.description,
                    "parameters": s.parameters,
                    "stage": s.stage,
                    "rationale": s.rationale,
                    "qc_focus": s.qc_focus,
                    "expected_output": s.expected_output,
                }
                for s in diff.removed_steps
            ],
            "modified_steps": diff.modified_steps,
            "metadata_changes": diff.metadata_changes,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/revision/save", methods=["POST"])
def api_save_revision():
    """Save current flow as a revision."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "JSON body required"}), 400

        if "flow" in data:
            flow = dict_to_flow(data["flow"])
        elif "flow" in _last_flow:
            flow = _last_flow["flow"]
        else:
            return jsonify({"error": "No flow available to save"}), 400

        author = data.get("author", "")
        changes = data.get("changes", "")

        rev = _revision_tracker.save_revision(flow, author=author, changes=changes)
        return jsonify({
            "version": rev.version,
            "timestamp": rev.timestamp,
            "author": rev.author,
            "changes": rev.changes,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/revision/history", methods=["GET"])
def api_revision_history():
    """Get revision history."""
    try:
        history = _revision_tracker.get_history()
        return jsonify({"revisions": history})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/revision/<int:version>", methods=["GET"])
def api_revision_get(version):
    """Return a saved revision snapshot as a flow payload."""
    try:
        revision = _revision_tracker.get_revision(version)
        return jsonify(flow_to_dict(dict_to_flow(revision.flow_snapshot)))
    except Exception as e:
        return jsonify({"error": str(e)}), 404


@app.route("/api/validate_params", methods=["POST"])
def api_validate_params():
    """Validate flow parameters against known rules."""
    try:
        data = request.get_json()
        if not data or "steps" not in data:
            return jsonify({"error": "JSON body with flow data required"}), 400

        flow = dict_to_flow(data)
        result = validate_flow_parameters(flow)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/statistics", methods=["POST"])
def api_statistics():
    """Get flow statistics."""
    try:
        data = request.get_json()
        if not data or "steps" not in data:
            return jsonify({"error": "JSON body with flow data required"}), 400

        flow = dict_to_flow(data)
        stats = get_flow_statistics(flow)
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/export_excel", methods=["POST"])
def api_export_excel():
    """Export flow to Excel workbook."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "JSON body required"}), 400

        flow = dict_to_flow(data)

        tmp = tempfile.NamedTemporaryFile(
            suffix=".xlsx", delete=False, prefix="report_"
        )
        tmp_path = tmp.name
        tmp.close()

        generate_excel_report(flow, tmp_path)

        data_type = flow.data_type or "SBP"
        project = flow.project_name.replace(" ", "_") if flow.project_name else ""
        if project:
            filename = f"Processing_Report_{data_type}_{project}.xlsx"
        else:
            filename = f"Processing_Report_{data_type}.xlsx"

        return send_file(
            tmp_path,
            as_attachment=True,
            download_name=filename,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/export_json", methods=["POST"])
def api_export_json():
    """Export flow as JSON."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "JSON body required"}), 400

        flow = dict_to_flow(data)
        json_str = generate_json_export(flow)
        json_data = json.loads(json_str)
        return jsonify(json_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/export_html", methods=["POST"])
def api_export_html():
    """Export flow as standalone HTML report."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "JSON body required"}), 400

        flow = dict_to_flow(data)
        html = generate_html_report(flow)
        return html, 200, {"Content-Type": "text/html; charset=utf-8"}
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/bulk_templates", methods=["POST"])
def api_bulk_templates():
    """Generate templates for all data types at once."""
    try:
        data = request.get_json(silent=True) or {}
        project_name = data.get("project_name", "")
        client = data.get("client", "")
        vessel = data.get("vessel", "")
        area = data.get("area", "")

        flows = generate_all_templates(
            project_name=project_name,
            client=client,
            vessel=vessel,
            area=area,
        )

        result = {}
        for dt, flow in flows.items():
            result[dt] = flow_to_dict(flow)

        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/bulk_download", methods=["POST"])
def api_bulk_download():
    """Generate DOCX reports for all data types and return as ZIP."""
    try:
        data = request.get_json(silent=True) or {}
        project_name = data.get("project_name", "")
        client = data.get("client", "")
        vessel = data.get("vessel", "")
        area = data.get("area", "")

        flows = generate_all_templates(
            project_name=project_name,
            client=client,
            vessel=vessel,
            area=area,
        )

        # Create ZIP in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for dt, flow in flows.items():
                tmp = tempfile.NamedTemporaryFile(
                    suffix=".docx", delete=False, prefix=f"report_{dt}_"
                )
                tmp_path = tmp.name
                tmp.close()
                generate_docx_report(flow, tmp_path)
                filename = f"Processing_Report_{dt}.docx"
                zf.write(tmp_path, filename)
                os.unlink(tmp_path)

        zip_buffer.seek(0)

        return send_file(
            zip_buffer,
            as_attachment=True,
            download_name="Processing_Reports_All.zip",
            mimetype="application/zip",
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def run_server(port=5404, debug=False):
    """Run the Flask development server."""
    try:
        from waitress import serve

        print(f" * ProcessingReportDraft Web GUI")
        print(f" * Running on http://127.0.0.1:{port}")
        print(f" * Press Ctrl+C to quit")
        serve(app, host="0.0.0.0", port=port)
    except ImportError:
        app.run(host="0.0.0.0", port=port, debug=debug)


if __name__ == "__main__":
    run_server()
