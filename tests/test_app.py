"""Tests for ProcessingReportDraft Flask web app — v2.0 expanded."""
import os
import sys
import json
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


@pytest.fixture
def client():
    from app import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_index_page(client):
    rv = client.get("/")
    assert rv.status_code == 200


def test_api_data_types(client):
    rv = client.get("/api/data_types")
    assert rv.status_code == 200
    data = json.loads(rv.data)
    assert data["ok"] is True
    assert "SBP" in data["supported"]
    assert "MBES" in data["supported"]
    assert "MAG" in data["supported"]
    assert "SSS" in data["supported"]


def test_api_data_types_has_details(client):
    rv = client.get("/api/data_types")
    data = json.loads(rv.data)
    assert "details" in data
    assert "SBP" in data["details"]
    assert "step_count" in data["details"]["SBP"]


def test_api_template_sbp(client):
    rv = client.post("/api/template",
                     data=json.dumps({"data_type": "SBP", "project_name": "Test Project"}),
                     content_type="application/json")
    assert rv.status_code == 200
    data = json.loads(rv.data)
    assert data["data_type"] == "SBP"
    assert data["project_name"] == "Test Project"
    assert len(data["steps"]) > 0


def test_api_template_uhr(client):
    rv = client.post("/api/template",
                     data=json.dumps({"data_type": "UHR"}),
                     content_type="application/json")
    assert rv.status_code == 200
    data = json.loads(rv.data)
    assert data["data_type"] == "UHR"
    assert len(data["steps"]) > 0


def test_api_template_mbes(client):
    rv = client.post("/api/template",
                     data=json.dumps({"data_type": "MBES", "project_name": "MBES Survey"}),
                     content_type="application/json")
    assert rv.status_code == 200
    data = json.loads(rv.data)
    assert data["data_type"] == "MBES"
    assert len(data["steps"]) >= 8


def test_api_template_mag(client):
    rv = client.post("/api/template",
                     data=json.dumps({"data_type": "MAG"}),
                     content_type="application/json")
    assert rv.status_code == 200
    data = json.loads(rv.data)
    assert data["data_type"] == "MAG"
    assert len(data["steps"]) >= 8


def test_api_template_sss(client):
    rv = client.post("/api/template",
                     data=json.dumps({"data_type": "SSS"}),
                     content_type="application/json")
    assert rv.status_code == 200
    data = json.loads(rv.data)
    assert data["data_type"] == "SSS"
    assert len(data["steps"]) >= 8


def test_api_template_no_body(client):
    rv = client.post("/api/template",
                     data="",
                     content_type="application/json")
    assert rv.status_code in (400, 500)


def test_api_template_applies_metadata(client):
    rv = client.post("/api/template",
                     data=json.dumps({
                         "data_type": "SBP",
                         "project_name": "My Project",
                         "client": "ClientA",
                         "vessel": "Vessel1",
                         "area": "East Sea",
                         "line_count": 50,
                     }),
                     content_type="application/json")
    data = json.loads(rv.data)
    assert data["project_name"] == "My Project"
    assert data["client"] == "ClientA"
    assert data["vessel"] == "Vessel1"
    assert data["area"] == "East Sea"
    assert data["line_count"] == 50


def test_api_parse_valid(client):
    log_text = """Project: Offshore Survey
Client: TestCorp
Data Type: SBP

1. SEG-Y Input
2. Bandpass Filter
3. Gain Control
"""
    rv = client.post("/api/parse",
                     data=json.dumps({"log_text": log_text}),
                     content_type="application/json")
    assert rv.status_code == 200
    data = json.loads(rv.data)
    assert len(data["steps"]) >= 3
    assert data["project_name"] == "Offshore Survey"


def test_api_parse_empty(client):
    rv = client.post("/api/parse",
                     data=json.dumps({"log_text": ""}),
                     content_type="application/json")
    assert rv.status_code == 400


def test_api_parse_with_parameters(client):
    log_text = """1. Filter
   Type: Butterworth
   Freq: 200 Hz
"""
    rv = client.post("/api/parse",
                     data=json.dumps({"log_text": log_text}),
                     content_type="application/json")
    data = json.loads(rv.data)
    assert data["steps"][0]["parameters"]["Type"] == "Butterworth"


def test_api_download_sbp(client):
    payload = {
        "project_name": "Test",
        "client": "Client A",
        "data_type": "SBP",
        "vessel": "Vessel X",
        "area": "East Sea",
        "date": "2025-01-01",
        "software": "RadExPro",
        "software_version": "5.0",
        "line_count": 100,
        "notes": "Test note",
        "steps": [
            {"order": 1, "name": "Input", "description": "Load SEG-Y", "parameters": {}},
            {"order": 2, "name": "Filter", "description": "Bandpass", "parameters": {"low": "50", "high": "500"}},
        ],
    }
    rv = client.post("/api/download",
                     data=json.dumps(payload),
                     content_type="application/json")
    assert rv.status_code == 200
    assert b"PK" in rv.data[:4]  # DOCX is a ZIP file


def test_api_download_mbes(client):
    payload = {
        "project_name": "MBES Report",
        "data_type": "MBES",
        "steps": [
            {"order": 1, "name": "Import", "description": "Load .all files", "parameters": {}},
        ],
    }
    rv = client.post("/api/download",
                     data=json.dumps(payload),
                     content_type="application/json")
    assert rv.status_code == 200
    assert b"PK" in rv.data[:4]


def test_api_download_no_body(client):
    rv = client.post("/api/download",
                     data="",
                     content_type="application/json")
    assert rv.status_code in (400, 500)


def test_api_export_text_with_flow(client):
    payload = {
        "project_name": "Text Export Test",
        "data_type": "SBP",
        "steps": [
            {"order": 1, "name": "Input", "description": "Load data", "parameters": {}},
            {"order": 2, "name": "Filter", "description": "Bandpass", "parameters": {}},
        ],
    }
    rv = client.post("/api/export_text",
                     data=json.dumps(payload),
                     content_type="application/json")
    assert rv.status_code == 200
    assert b"ProcessingReportDraft" in rv.data
    assert b"Text Export Test" in rv.data


def test_api_export_text_after_template(client):
    """Export text after generating a template (uses stored flow)."""
    client.post("/api/template",
                data=json.dumps({"data_type": "MBES", "project_name": "Stored Flow"}),
                content_type="application/json")
    rv = client.post("/api/export_text",
                     data=json.dumps({}),
                     content_type="application/json")
    assert rv.status_code == 200
    assert b"ProcessingReportDraft" in rv.data


def test_api_export_text_no_flow(client):
    """Export text with no stored flow and no data returns error or uses stored."""
    rv = client.post("/api/export_text",
                     data=json.dumps({}),
                     content_type="application/json")
    # Could be 400 or 200 depending on global state
    assert rv.status_code in [200, 400]


def test_api_template_step_count(client):
    rv = client.post("/api/template",
                     data=json.dumps({"data_type": "SBP"}),
                     content_type="application/json")
    data = json.loads(rv.data)
    assert data["step_count"] == len(data["steps"])


def test_api_download_filename_contains_type(client):
    payload = {
        "project_name": "MyProject",
        "data_type": "MAG",
        "steps": [],
    }
    rv = client.post("/api/download",
                     data=json.dumps(payload),
                     content_type="application/json")
    assert rv.status_code == 200
    content_disp = rv.headers.get("Content-Disposition", "")
    assert "MAG" in content_disp
    assert "MyProject" in content_disp


# ── Step Editing API Tests ──

def test_api_add_step(client):
    # First create a template flow
    client.post("/api/template",
                data=json.dumps({"data_type": "SBP"}),
                content_type="application/json")
    # Add a custom step
    rv = client.post("/api/step/add",
                     data=json.dumps({"name": "Custom Filter", "description": "My filter", "parameters": {"type": "custom"}}),
                     content_type="application/json")
    assert rv.status_code == 200
    data = json.loads(rv.data)
    assert data["steps"][-1]["name"] == "Custom Filter"
    assert data["steps"][-1]["parameters"]["type"] == "custom"


def test_api_remove_step(client):
    # Create a template flow
    client.post("/api/template",
                data=json.dumps({"data_type": "SBP"}),
                content_type="application/json")
    # Remove step 1
    rv = client.post("/api/step/remove",
                     data=json.dumps({"order": 1}),
                     content_type="application/json")
    assert rv.status_code == 200
    data = json.loads(rv.data)
    # First step should no longer be "Data Input"
    assert data["steps"][0]["name"] != "Data Input"
    assert data["steps"][0]["order"] == 1  # renumbered


def test_api_reorder_steps(client):
    # Create a small flow via template then remove extra steps for simplicity
    payload = {
        "flow": {
            "project_name": "Test",
            "data_type": "SBP",
            "steps": [
                {"order": 1, "name": "A", "description": "", "parameters": {}},
                {"order": 2, "name": "B", "description": "", "parameters": {}},
                {"order": 3, "name": "C", "description": "", "parameters": {}},
            ],
        },
        "new_order": [3, 1, 2],
    }
    rv = client.post("/api/step/reorder",
                     data=json.dumps(payload),
                     content_type="application/json")
    assert rv.status_code == 200
    data = json.loads(rv.data)
    assert data["steps"][0]["name"] == "C"
    assert data["steps"][1]["name"] == "A"
    assert data["steps"][2]["name"] == "B"


def test_api_update_step(client):
    # Create a flow with inline data
    payload = {
        "flow": {
            "project_name": "Test",
            "data_type": "SBP",
            "steps": [
                {"order": 1, "name": "Old Name", "description": "old desc", "parameters": {}},
            ],
        },
        "order": 1,
        "name": "New Name",
        "description": "new desc",
    }
    rv = client.post("/api/step/update",
                     data=json.dumps(payload),
                     content_type="application/json")
    assert rv.status_code == 200
    data = json.loads(rv.data)
    assert data["steps"][0]["name"] == "New Name"
    assert data["steps"][0]["description"] == "new desc"


def test_api_compare_flows(client):
    flow1 = {
        "project_name": "Project A",
        "data_type": "SBP",
        "steps": [
            {"order": 1, "name": "Input", "description": "", "parameters": {"format": "SEG-Y"}},
            {"order": 2, "name": "Filter", "description": "", "parameters": {}},
        ],
    }
    flow2 = {
        "project_name": "Project B",
        "data_type": "SBP",
        "steps": [
            {"order": 1, "name": "Input", "description": "", "parameters": {"format": "SEG-D"}},
            {"order": 2, "name": "Export", "description": "", "parameters": {}},
        ],
    }
    rv = client.post("/api/compare_flows",
                     data=json.dumps({"flow1": flow1, "flow2": flow2}),
                     content_type="application/json")
    assert rv.status_code == 200
    data = json.loads(rv.data)
    assert "project_name" in data["metadata_changes"]
    assert len(data["added_steps"]) == 1  # Export is new
    assert len(data["removed_steps"]) == 1  # Filter is removed
    assert len(data["modified_steps"]) == 1  # Input has different params


def test_api_save_revision(client):
    # First create a flow
    client.post("/api/template",
                data=json.dumps({"data_type": "SBP", "project_name": "Rev Test"}),
                content_type="application/json")
    rv = client.post("/api/revision/save",
                     data=json.dumps({"author": "Kim", "changes": "Initial version"}),
                     content_type="application/json")
    assert rv.status_code == 200
    data = json.loads(rv.data)
    assert data["version"] >= 1
    assert data["author"] == "Kim"
    assert data["changes"] == "Initial version"


def test_api_revision_history(client):
    # Save a revision first
    client.post("/api/template",
                data=json.dumps({"data_type": "SBP", "project_name": "History Test"}),
                content_type="application/json")
    client.post("/api/revision/save",
                data=json.dumps({"author": "Test", "changes": "test revision"}),
                content_type="application/json")
    rv = client.get("/api/revision/history")
    assert rv.status_code == 200
    data = json.loads(rv.data)
    assert "revisions" in data
    assert len(data["revisions"]) >= 1


def test_api_step_add_to_empty_flow(client):
    """Adding a step when no flow exists should create one."""
    # Reset the stored flow by posting an empty template
    # Use a fresh client where _last_flow might be empty
    rv = client.post("/api/step/add",
                     data=json.dumps({
                         "name": "First Step",
                         "description": "The very first step",
                         "parameters": {"key": "value"},
                         "flow": {
                             "project_name": "",
                             "data_type": "SBP",
                             "steps": [],
                         },
                     }),
                     content_type="application/json")
    assert rv.status_code == 200
    data = json.loads(rv.data)
    assert len(data["steps"]) == 1
    assert data["steps"][0]["name"] == "First Step"
    assert data["steps"][0]["order"] == 1


# ── Parameter Validation API Tests ──

def test_api_validate_params(client):
    rv = client.post("/api/template",
                     data=json.dumps({"data_type": "SBP", "project_name": "Test"}),
                     content_type="application/json")
    flow = json.loads(rv.data)
    rv2 = client.post("/api/validate_params",
                      data=json.dumps(flow),
                      content_type="application/json")
    assert rv2.status_code == 200
    data = json.loads(rv2.data)
    assert "score" in data
    assert "total_params_checked" in data
    assert "issues" in data


def test_api_validate_params_no_body(client):
    rv = client.post("/api/validate_params",
                     data=json.dumps({}),
                     content_type="application/json")
    assert rv.status_code in (400, 500)


# ── Statistics API Tests ──

def test_api_statistics(client):
    rv = client.post("/api/template",
                     data=json.dumps({"data_type": "SBP"}),
                     content_type="application/json")
    flow = json.loads(rv.data)
    rv2 = client.post("/api/statistics",
                      data=json.dumps(flow),
                      content_type="application/json")
    assert rv2.status_code == 200
    data = json.loads(rv2.data)
    assert data["step_count"] >= 8
    assert "completeness_score" in data
    assert "parameter_types" in data


# ── Export API Tests ──

def test_api_export_excel(client):
    rv = client.post("/api/template",
                     data=json.dumps({"data_type": "SBP", "project_name": "Test"}),
                     content_type="application/json")
    flow = json.loads(rv.data)
    rv2 = client.post("/api/export_excel",
                      data=json.dumps(flow),
                      content_type="application/json")
    assert rv2.status_code == 200
    # XLSX files start with PK (zip magic bytes)
    assert rv2.data[:2] == b"PK"


def test_api_export_json(client):
    rv = client.post("/api/template",
                     data=json.dumps({"data_type": "SBP"}),
                     content_type="application/json")
    flow = json.loads(rv.data)
    rv2 = client.post("/api/export_json",
                      data=json.dumps(flow),
                      content_type="application/json")
    assert rv2.status_code == 200
    data = json.loads(rv2.data)
    assert data["data_type"] == "SBP"
    assert len(data["steps"]) >= 8


def test_api_export_html(client):
    rv = client.post("/api/template",
                     data=json.dumps({"data_type": "SBP"}),
                     content_type="application/json")
    flow = json.loads(rv.data)
    rv2 = client.post("/api/export_html",
                      data=json.dumps(flow),
                      content_type="application/json")
    assert rv2.status_code == 200
    assert b"<html" in rv2.data
    assert b"SBP" in rv2.data


# ── Bulk Template API Tests ──

def test_api_bulk_templates(client):
    rv = client.post("/api/bulk_templates",
                     data=json.dumps({"project_name": "BulkTest"}),
                     content_type="application/json")
    assert rv.status_code == 200
    data = json.loads(rv.data)
    assert len(data) == 5
    assert "SBP" in data
    assert "UHR" in data
    assert "MBES" in data
    assert "MAG" in data
    assert "SSS" in data
    assert data["SBP"]["project_name"] == "BulkTest"


def test_api_bulk_templates_empty(client):
    rv = client.post("/api/bulk_templates",
                     data=json.dumps({}),
                     content_type="application/json")
    assert rv.status_code == 200
    data = json.loads(rv.data)
    assert len(data) == 5


def test_api_bulk_download(client):
    rv = client.post("/api/bulk_download",
                     data=json.dumps({"project_name": "Test"}),
                     content_type="application/json")
    assert rv.status_code == 200
    # Should return a zip file
    assert rv.data[:2] == b"PK"  # ZIP magic bytes
