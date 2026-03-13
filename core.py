"""Core engine for Processing Report Draft generation."""
import copy
import html
import json
import os
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional


@dataclass
class ProcessingStep:
    order: int
    name: str
    description: str = ""
    parameters: dict = field(default_factory=dict)


@dataclass
class ProcessingFlow:
    project_name: str = ""
    client: str = ""
    data_type: str = "SBP"
    vessel: str = ""
    area: str = ""
    date: str = ""
    software: str = "RadExPro"
    software_version: str = ""
    steps: list = field(default_factory=list)
    line_count: int = 0
    notes: str = ""

    @property
    def step_count(self):
        return len(self.steps)


# Common RadExPro processing steps for SBP
DEFAULT_SBP_STEPS = [
    ProcessingStep(1, "Data Input", "SEG-Y data loading and header mapping", {
        "Input format": "SEG-Y Rev 1",
        "Byte order": "Big Endian",
    }),
    ProcessingStep(2, "Geometry Assignment", "Navigation data application and coordinate system setup", {
        "Coordinate system": "WGS84 / UTM",
        "Navigation source": "Embedded in trace headers",
    }),
    ProcessingStep(3, "Trace Editing", "Bad trace removal and data cleanup", {
        "Method": "Manual + automatic spike detection",
    }),
    ProcessingStep(4, "Band-pass Filter", "Frequency filtering to remove noise", {
        "Type": "Ormsby / Butterworth",
        "Low cut": "TBD Hz",
        "High cut": "TBD Hz",
    }),
    ProcessingStep(5, "Gain Application", "Time-varying gain to compensate for amplitude decay", {
        "Type": "AGC / TVG",
        "Window": "TBD ms",
    }),
    ProcessingStep(6, "Swell Filter / Heave Compensation", "Removal of swell-induced noise", {
        "Method": "Swell filter / Static correction",
    }),
    ProcessingStep(7, "Deconvolution", "Source signature removal for improved resolution", {
        "Type": "Predictive / Spiking",
        "Operator length": "TBD ms",
    }),
    ProcessingStep(8, "Migration", "Spatial repositioning of reflectors", {
        "Type": "Stolt / Kirchhoff",
        "Velocity": "TBD m/s",
    }),
    ProcessingStep(9, "Mute / Seafloor Tracking", "Definition of seafloor horizon and muting above", {
        "Method": "Automatic + manual correction",
    }),
    ProcessingStep(10, "SEG-Y Output", "Final processed data export", {
        "Output format": "SEG-Y Rev 1",
        "Sample format": "IEEE 32-bit float",
    }),
]

DEFAULT_UHR_STEPS = [
    ProcessingStep(1, "Data Input", "Multi-channel SEG-D/SEG-Y loading", {
        "Input format": "SEG-Y / SEG-D",
        "Channels": "TBD",
    }),
    ProcessingStep(2, "Geometry Assignment", "Source-receiver geometry and navigation", {
        "Source-receiver offset": "TBD m",
        "Streamer length": "TBD m",
    }),
    ProcessingStep(3, "Trace Editing", "Noisy trace removal and QC", {}),
    ProcessingStep(4, "Band-pass Filter", "Frequency domain filtering", {
        "Low cut": "TBD Hz",
        "High cut": "TBD Hz",
    }),
    ProcessingStep(5, "Gain / AGC", "Amplitude compensation", {
        "AGC window": "TBD ms",
    }),
    ProcessingStep(6, "Deconvolution", "Wavelet compression", {}),
    ProcessingStep(7, "Velocity Analysis", "Velocity picking and NMO correction", {
        "Method": "Semblance analysis",
        "Interval": "Every TBD CDPs",
    }),
    ProcessingStep(8, "NMO Correction", "Normal moveout correction", {}),
    ProcessingStep(9, "CMP Stack", "Common midpoint stacking", {
        "Fold": "TBD",
    }),
    ProcessingStep(10, "Migration", "Post-stack time migration", {
        "Type": "Stolt / Kirchhoff",
        "Velocity model": "Stacking velocities",
    }),
    ProcessingStep(11, "Post-Stack Processing", "Final filtering and scaling", {}),
    ProcessingStep(12, "SEG-Y Output", "Final export", {
        "Output format": "SEG-Y Rev 1",
    }),
]


DEFAULT_MBES_STEPS = [
    ProcessingStep(1, "Data Import", "Raw multibeam data import from acquisition system", {
        "Format": "*.all / *.s7k / *.db / *.kmall",
        "Software": "CARIS HIPS / QPS Qimera",
    }),
    ProcessingStep(2, "Navigation QC", "Vessel position data validation and smoothing", {
        "Position source": "DGPS / PPK",
        "Accuracy": "TBD m",
    }),
    ProcessingStep(3, "Sound Velocity Profile", "SVP application for ray tracing correction", {
        "SVP source": "CTD / SVP cast",
        "Application method": "Nearest in distance/time",
    }),
    ProcessingStep(4, "Tide Correction", "Water level correction to chart datum", {
        "Tide source": "Observed / Predicted / RTK",
        "Datum": "LAT / MSL / CD",
    }),
    ProcessingStep(5, "Vessel Configuration", "Lever arm offsets and mounting angles", {
        "IMU-transducer offsets": "TBD m",
        "Patch test applied": "Yes / No",
    }),
    ProcessingStep(6, "Swath Editing", "Outlier removal and noise cleaning", {
        "Method": "Automatic + Manual",
        "Filter type": "Median / CUBE / Surface",
    }),
    ProcessingStep(7, "Surface Generation", "Bathymetric surface creation", {
        "Resolution": "TBD m",
        "Method": "Weighted Mean / CUBE / Shoal Bias",
    }),
    ProcessingStep(8, "Quality Assessment", "IHO S-44 or project-specific accuracy check", {
        "Standard": "IHO S-44 Special Order / Order 1a / 1b",
        "THU/TVU": "TBD m",
    }),
    ProcessingStep(9, "Export", "Final product export", {
        "Output format": "GeoTIFF / BAG / XYZ / ASCII",
        "Coordinate system": "WGS84 / UTM Zone TBD",
    }),
]


DEFAULT_MAG_STEPS = [
    ProcessingStep(1, "Data Import", "Raw magnetometer data import", {
        "Format": "ASCII / Binary / MagLog",
        "Sensor type": "Proton / Overhauser / Cesium",
    }),
    ProcessingStep(2, "Navigation Merge", "Merge mag readings with vessel positioning", {
        "Layback": "TBD m",
        "Position source": "DGPS",
    }),
    ProcessingStep(3, "Diurnal Correction", "Removal of temporal magnetic field variation", {
        "Base station": "Yes / No",
        "Source": "Local base / INTERMAGNET",
    }),
    ProcessingStep(4, "Spike Removal", "Remove erroneous readings and dropouts", {
        "Method": "Threshold / 4th difference",
        "Threshold": "TBD nT",
    }),
    ProcessingStep(5, "IGRF Removal", "Subtraction of International Geomagnetic Reference Field", {
        "IGRF model": "IGRF-13 / WMM",
        "Epoch": "TBD",
    }),
    ProcessingStep(6, "Heading Correction", "Compensation for sensor heading effects", {
        "Method": "Line-based correction",
    }),
    ProcessingStep(7, "Leveling", "Cross-line/tie-line leveling for consistency", {
        "Method": "Statistical / Polynomial",
        "Tie lines used": "TBD",
    }),
    ProcessingStep(8, "Gridding", "Magnetic anomaly grid generation", {
        "Grid size": "TBD m",
        "Method": "Minimum curvature / Kriging",
    }),
    ProcessingStep(9, "Analytic Signal", "Derivative products for interpretation", {
        "Products": "Total gradient / Tilt derivative / RTP",
    }),
    ProcessingStep(10, "Export", "Final product export", {
        "Output format": "GeoTIFF / XYZ / Geosoft Grid",
    }),
]


DEFAULT_SSS_STEPS = [
    ProcessingStep(1, "Data Import", "Raw side scan sonar data import", {
        "Format": "XTF / JSF / SDF",
        "Frequency": "TBD kHz",
    }),
    ProcessingStep(2, "Navigation QC", "Towfish position and layback correction", {
        "Layback method": "Cable out / USBL",
        "Positioning": "DGPS",
    }),
    ProcessingStep(3, "Slant Range Correction", "Geometric correction for water column", {
        "Method": "Flat bottom / DTM-based",
        "Towfish altitude": "TBD m",
    }),
    ProcessingStep(4, "Gain Normalization", "Along-track and across-track gain correction", {
        "TVG": "Applied / Not applied",
        "EGN": "Empirical Gain Normalization",
    }),
    ProcessingStep(5, "Speed Correction", "Along-track distortion correction", {
        "Speed source": "GPS SOG / vessel speed",
    }),
    ProcessingStep(6, "Bottom Tracking", "Automatic seafloor detection and nadir removal", {
        "Method": "Automatic + Manual QC",
    }),
    ProcessingStep(7, "Mosaicking", "Image mosaic generation", {
        "Resolution": "TBD m/pixel",
        "Blending": "Feathered / Nadir priority",
    }),
    ProcessingStep(8, "Contact Detection", "Target identification and reporting", {
        "Method": "Automatic + Manual",
        "Classification": "Boulder / Debris / Cable / Unknown",
    }),
    ProcessingStep(9, "Export", "Final mosaic and contact report export", {
        "Output format": "GeoTIFF / KMZ / Shapefile",
    }),
]


# Supported data types and their templates
DATA_TYPE_TEMPLATES = {
    "SBP": DEFAULT_SBP_STEPS,
    "UHR": DEFAULT_UHR_STEPS,
    "UHRS": DEFAULT_UHR_STEPS,
    "2DHR": DEFAULT_UHR_STEPS,
    "MBES": DEFAULT_MBES_STEPS,
    "MULTIBEAM": DEFAULT_MBES_STEPS,
    "MAG": DEFAULT_MAG_STEPS,
    "MAGNETICS": DEFAULT_MAG_STEPS,
    "SSS": DEFAULT_SSS_STEPS,
    "SIDESCAN": DEFAULT_SSS_STEPS,
}

SUPPORTED_DATA_TYPES = sorted(set(DATA_TYPE_TEMPLATES.keys()))


def parse_processing_log(log_text):
    """Parse a text-based processing log into ProcessingFlow.

    Supports formats:
    - Simple numbered steps: "1. Step Name - Description"
    - Key: Value pairs for parameters
    - YAML-like structures
    """
    flow = ProcessingFlow()
    steps = []
    current_step = None
    order = 0

    for line in log_text.split("\n"):
        line = line.strip()
        if not line:
            continue

        # Check for project metadata
        lower = line.lower()
        if current_step is None:
            if lower.startswith("project:"):
                flow.project_name = line.split(":", 1)[1].strip()
                continue
            elif lower.startswith("client:"):
                flow.client = line.split(":", 1)[1].strip()
                continue
            elif lower.startswith("data type:") or lower.startswith("type:"):
                flow.data_type = line.split(":", 1)[1].strip()
                continue
            elif lower.startswith("vessel:"):
                flow.vessel = line.split(":", 1)[1].strip()
                continue
            elif lower.startswith("area:"):
                flow.area = line.split(":", 1)[1].strip()
                continue
            elif lower.startswith("software:"):
                flow.software = line.split(":", 1)[1].strip()
                continue
            elif lower.startswith("lines:") or lower.startswith("line count:"):
                try:
                    flow.line_count = int(re.search(r"\d+", line.split(":", 1)[1]).group())
                except (AttributeError, ValueError):
                    pass
                continue

        # Check for numbered step
        step_match = re.match(r"^(\d+)[.)\s]+(.+)", line)
        if step_match:
            if current_step:
                steps.append(current_step)
            order += 1
            name = step_match.group(2).strip()
            desc = ""
            if " - " in name:
                name, desc = name.split(" - ", 1)
            elif ": " in name:
                name, desc = name.split(": ", 1)
            current_step = ProcessingStep(order=order, name=name.strip(), description=desc.strip())
            continue

        # Check for parameter (indented key:value)
        if current_step and ":" in line and not line.startswith("#"):
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip()
            if key and val:
                current_step.parameters[key] = val

    if current_step:
        steps.append(current_step)

    flow.steps = steps
    return flow


def generate_docx_report(flow, output_path):
    """Generate a Word document processing report draft."""
    from docx import Document
    from docx.shared import Inches, Pt, Cm
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT

    doc = Document()

    # Page setup
    section = doc.sections[0]
    section.top_margin = Cm(2.5)
    section.bottom_margin = Cm(2.5)
    section.left_margin = Cm(2.5)
    section.right_margin = Cm(2.5)

    # Title
    title = doc.add_heading(level=0)
    run = title.add_run("Data Processing Report")
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Subtitle
    if flow.project_name:
        subtitle = doc.add_paragraph()
        subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = subtitle.add_run(flow.project_name)
        run.font.size = Pt(16)

    doc.add_paragraph()

    # Project Information table
    doc.add_heading("1. Project Information", level=1)
    info_data = [
        ("Project Name", flow.project_name or "TBD"),
        ("Client", flow.client or "TBD"),
        ("Data Type", flow.data_type or "TBD"),
        ("Vessel", flow.vessel or "TBD"),
        ("Survey Area", flow.area or "TBD"),
        ("Processing Software", f"{flow.software} {flow.software_version}".strip()),
        ("Number of Lines", str(flow.line_count) if flow.line_count else "TBD"),
        ("Report Date", datetime.now().strftime("%Y-%m-%d")),
    ]

    table = doc.add_table(rows=len(info_data), cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, (key, val) in enumerate(info_data):
        table.rows[i].cells[0].text = key
        table.rows[i].cells[1].text = val
        # Bold the key
        for paragraph in table.rows[i].cells[0].paragraphs:
            for run in paragraph.runs:
                run.bold = True

    doc.add_paragraph()

    # Processing Flow
    doc.add_heading("2. Processing Flow", level=1)

    if flow.steps:
        # Flow summary
        p = doc.add_paragraph()
        p.add_run(f"The processing sequence consists of {len(flow.steps)} steps as described below.")

        for step in flow.steps:
            doc.add_heading(f"2.{step.order}  {step.name}", level=2)

            if step.description:
                doc.add_paragraph(step.description)

            if step.parameters:
                param_table = doc.add_table(rows=len(step.parameters) + 1, cols=2)
                param_table.alignment = WD_TABLE_ALIGNMENT.CENTER

                # Header row
                param_table.rows[0].cells[0].text = "Parameter"
                param_table.rows[0].cells[1].text = "Value"
                for cell in param_table.rows[0].cells:
                    for paragraph in cell.paragraphs:
                        for run in paragraph.runs:
                            run.bold = True

                for j, (key, val) in enumerate(step.parameters.items(), 1):
                    param_table.rows[j].cells[0].text = key
                    param_table.rows[j].cells[1].text = str(val)

                doc.add_paragraph()
    else:
        doc.add_paragraph("[Processing steps to be added]")

    # Quality Control
    doc.add_heading("3. Quality Control", level=1)
    doc.add_paragraph(
        "Quality control was performed at each processing stage. "
        "The following QC checks were applied:"
    )
    qc_items = [
        "Navigation QC: Position continuity and coordinate validation",
        "Amplitude QC: RMS amplitude consistency across lines",
        "Frequency QC: Spectral analysis before and after filtering",
        "Noise QC: Signal-to-noise ratio evaluation",
        "Final visual QC: Inspection of all processed lines",
    ]
    for item in qc_items:
        doc.add_paragraph(item, style="List Bullet")

    doc.add_paragraph()

    # Results Summary
    doc.add_heading("4. Results Summary", level=1)
    doc.add_paragraph("[Summary of processing results to be added]")

    # Appendix
    doc.add_heading("Appendix A: Processing Flow Diagram", level=1)
    doc.add_paragraph("[Insert processing flow diagram]")

    doc.add_heading("Appendix B: Line Summary", level=1)
    doc.add_paragraph("[Insert line processing summary table]")

    doc.save(output_path)
    return output_path


def generate_flow_from_template(data_type="SBP"):
    """Get a default processing flow template."""
    dt_upper = data_type.upper()
    flow = ProcessingFlow(data_type=data_type)

    template = DATA_TYPE_TEMPLATES.get(dt_upper, DEFAULT_SBP_STEPS)
    flow.steps = [copy.deepcopy(s) for s in template]

    # Set default software based on data type
    if dt_upper in ("MBES", "MULTIBEAM"):
        flow.software = "CARIS HIPS and SIPS"
    elif dt_upper in ("MAG", "MAGNETICS"):
        flow.software = "Oasis Montaj"
    elif dt_upper in ("SSS", "SIDESCAN"):
        flow.software = "SonarWiz / CARIS"
    else:
        flow.software = "RadExPro"

    return flow


def generate_text_report(flow):
    """Generate a plain text processing report."""
    lines = []
    lines.append("=" * 70)
    lines.append("  ProcessingReportDraft — Data Processing Report")
    lines.append("=" * 70)
    lines.append("")

    # Metadata
    lines.append(f"  Project:    {flow.project_name or 'TBD'}")
    lines.append(f"  Client:     {flow.client or 'TBD'}")
    lines.append(f"  Data Type:  {flow.data_type or 'TBD'}")
    lines.append(f"  Vessel:     {flow.vessel or 'TBD'}")
    lines.append(f"  Area:       {flow.area or 'TBD'}")
    lines.append(f"  Software:   {flow.software} {flow.software_version}".rstrip())
    lines.append(f"  Lines:      {flow.line_count or 'TBD'}")
    lines.append("")
    lines.append(f"{'─' * 70}")
    lines.append(f"  Processing Steps ({flow.step_count} steps)")
    lines.append(f"{'─' * 70}")

    for step in flow.steps:
        lines.append(f"\n  Step {step.order}: {step.name}")
        if step.description:
            lines.append(f"    {step.description}")
        if step.parameters:
            for k, v in step.parameters.items():
                lines.append(f"    • {k}: {v}")

    lines.append("")
    lines.append("=" * 70)
    if flow.notes:
        lines.append(f"\n  Notes: {flow.notes}")
    return "\n".join(lines)


def get_supported_types():
    """Return list of supported data types with info."""
    info = {}
    for dt, steps in DATA_TYPE_TEMPLATES.items():
        if dt not in info:
            info[dt] = {
                "name": dt,
                "step_count": len(steps),
                "steps_preview": [s.name for s in steps[:5]],
            }
    return info


# ── Custom Step Editing ──

def _renumber_steps(flow):
    """Re-number all steps sequentially starting from 1."""
    for i, step in enumerate(flow.steps):
        step.order = i + 1
    return flow


def add_custom_step(flow, name, description="", parameters=None, position=None):
    """Add a custom step to flow. If position is None, append to end.
    Auto-sets order numbers. Returns updated flow."""
    if parameters is None:
        parameters = {}
    new_step = ProcessingStep(order=0, name=name, description=description, parameters=parameters)
    if position is None or position > len(flow.steps):
        flow.steps.append(new_step)
    else:
        idx = max(0, position - 1)
        flow.steps.insert(idx, new_step)
    _renumber_steps(flow)
    return flow


def remove_step(flow, order):
    """Remove step by order number and re-number remaining steps.
    Returns updated flow."""
    flow.steps = [s for s in flow.steps if s.order != order]
    _renumber_steps(flow)
    return flow


def reorder_steps(flow, new_order):
    """Reorder steps. new_order is list of current order numbers in desired sequence.
    Example: [3,1,2] puts step 3 first, then 1, then 2.
    Returns updated flow."""
    order_map = {s.order: s for s in flow.steps}
    # Validate that all order numbers exist
    for o in new_order:
        if o not in order_map:
            raise ValueError(f"Step with order {o} does not exist")
    if len(new_order) != len(flow.steps):
        raise ValueError("new_order must contain all step order numbers")
    flow.steps = [order_map[o] for o in new_order]
    _renumber_steps(flow)
    return flow


def update_step(flow, order, name=None, description=None, parameters=None):
    """Update a specific step's properties. Returns updated flow."""
    for step in flow.steps:
        if step.order == order:
            if name is not None:
                step.name = name
            if description is not None:
                step.description = description
            if parameters is not None:
                step.parameters = parameters
            return flow
    raise ValueError(f"Step with order {order} not found")


# ── Flow Comparison ──

@dataclass
class FlowDiff:
    added_steps: list = field(default_factory=list)     # steps in flow2 not in flow1
    removed_steps: list = field(default_factory=list)    # steps in flow1 not in flow2
    modified_steps: list = field(default_factory=list)   # steps with different parameters
    metadata_changes: dict = field(default_factory=dict) # changes to project_name, client, etc.


def compare_flows(flow1, flow2):
    """Compare two ProcessingFlows and return differences."""
    diff = FlowDiff()

    # Compare metadata
    metadata_fields = [
        "project_name", "client", "data_type", "vessel",
        "area", "date", "software", "software_version",
        "line_count", "notes",
    ]
    for f in metadata_fields:
        v1 = getattr(flow1, f)
        v2 = getattr(flow2, f)
        if v1 != v2:
            diff.metadata_changes[f] = {"old": v1, "new": v2}

    # Build name-based maps for step comparison
    names1 = {s.name: s for s in flow1.steps}
    names2 = {s.name: s for s in flow2.steps}

    # Added: in flow2 but not flow1
    for name, step in names2.items():
        if name not in names1:
            diff.added_steps.append(step)

    # Removed: in flow1 but not flow2
    for name, step in names1.items():
        if name not in names2:
            diff.removed_steps.append(step)

    # Modified: same name but different parameters or description
    for name in names1:
        if name in names2:
            s1 = names1[name]
            s2 = names2[name]
            if s1.parameters != s2.parameters or s1.description != s2.description:
                diff.modified_steps.append({
                    "name": name,
                    "old": {"description": s1.description, "parameters": s1.parameters},
                    "new": {"description": s2.description, "parameters": s2.parameters},
                })

    return diff


# ── Revision Tracking ──

def _serialize_flow(flow):
    """Serialize a ProcessingFlow to a dict for storage."""
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
        "steps": [
            {
                "order": s.order,
                "name": s.name,
                "description": s.description,
                "parameters": dict(s.parameters),
            }
            for s in flow.steps
        ],
    }


def _deserialize_flow(d):
    """Deserialize a dict back to a ProcessingFlow."""
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
        )
        for i, s in enumerate(d.get("steps", []))
    ]
    return flow


@dataclass
class FlowRevision:
    version: int
    timestamp: str
    author: str
    changes: str  # description of changes
    flow_snapshot: dict = field(default_factory=dict)  # serialized flow at this point


class RevisionTracker:
    def __init__(self):
        self.revisions = []  # list of FlowRevision

    def save_revision(self, flow, author="", changes=""):
        """Save current flow as a new revision."""
        version = len(self.revisions) + 1
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        snapshot = _serialize_flow(flow)
        revision = FlowRevision(
            version=version,
            timestamp=timestamp,
            author=author,
            changes=changes,
            flow_snapshot=snapshot,
        )
        self.revisions.append(revision)
        return revision

    def get_revision(self, version):
        """Get a specific revision."""
        for rev in self.revisions:
            if rev.version == version:
                return rev
        raise ValueError(f"Revision version {version} not found")

    def get_history(self):
        """Get list of all revisions with metadata."""
        return [
            {
                "version": r.version,
                "timestamp": r.timestamp,
                "author": r.author,
                "changes": r.changes,
            }
            for r in self.revisions
        ]

    def diff_revisions(self, v1, v2):
        """Get diff between two revision versions."""
        rev1 = self.get_revision(v1)
        rev2 = self.get_revision(v2)
        flow1 = _deserialize_flow(rev1.flow_snapshot)
        flow2 = _deserialize_flow(rev2.flow_snapshot)
        return compare_flows(flow1, flow2)


# ── Step Parameter Validation ──

PARAMETER_VALIDATION_RULES = {
    "SBP": {
        "Band-pass Filter": {
            "Low Cut (Hz)": {"min": 0.1, "max": 500, "type": "float"},
            "High Cut (Hz)": {"min": 100, "max": 20000, "type": "float"},
            "Filter Type": {"allowed": ["Butterworth", "Ormsby", "Zero-phase"], "type": "choice"},
        },
        "Gain Application": {
            "AGC Window (ms)": {"min": 10, "max": 5000, "type": "float"},
        },
        "Migration": {
            "Velocity (m/s)": {"min": 1400, "max": 2000, "type": "float"},
        },
    },
    "UHR": {
        "Band-pass Filter": {
            "Low Cut (Hz)": {"min": 1, "max": 1000, "type": "float"},
            "High Cut (Hz)": {"min": 50, "max": 50000, "type": "float"},
        },
        "Velocity Analysis": {
            "CDP Interval": {"min": 1, "max": 100, "type": "int"},
        },
        "NMO Correction": {
            "Stretch Mute (%)": {"min": 5, "max": 100, "type": "float"},
        },
    },
    "MBES": {
        "Surface Generation": {
            "Cell Size (m)": {"min": 0.1, "max": 100, "type": "float"},
        },
    },
    "MAG": {
        "Spike Removal": {
            "Threshold (nT)": {"min": 1, "max": 10000, "type": "float"},
        },
        "Gridding": {
            "Cell Size (m)": {"min": 1, "max": 1000, "type": "float"},
        },
    },
}


def validate_flow_parameters(flow):
    """Validate all step parameters against known rules.

    Returns: {
        "total_params_checked": N,
        "valid": N,
        "invalid": N,
        "unknown": N,  # params not in rules (not an error)
        "issues": [
            {"step": str, "parameter": str, "value": str, "expected": str, "severity": "error"/"warning"}
        ],
        "score": float  # 0-100, percentage of valid params
    }
    """
    rules = PARAMETER_VALIDATION_RULES.get(flow.data_type, {})
    issues = []
    total = 0
    valid = 0
    invalid = 0
    unknown = 0

    for step in flow.steps:
        step_rules = rules.get(step.name, {})
        for param_name, param_value in step.parameters.items():
            total += 1
            if param_name not in step_rules:
                unknown += 1
                continue
            rule = step_rules[param_name]
            try:
                if rule["type"] == "choice":
                    if param_value not in rule["allowed"]:
                        invalid += 1
                        issues.append({
                            "step": step.name,
                            "parameter": param_name,
                            "value": str(param_value),
                            "expected": f"One of: {rule['allowed']}",
                            "severity": "error",
                        })
                    else:
                        valid += 1
                elif rule["type"] in ("float", "int"):
                    num_val = float(param_value) if isinstance(param_value, str) else param_value
                    if num_val < rule["min"] or num_val > rule["max"]:
                        invalid += 1
                        issues.append({
                            "step": step.name,
                            "parameter": param_name,
                            "value": str(param_value),
                            "expected": f"{rule['min']} - {rule['max']}",
                            "severity": "warning",
                        })
                    else:
                        valid += 1
                else:
                    unknown += 1
            except (ValueError, TypeError):
                invalid += 1
                issues.append({
                    "step": step.name,
                    "parameter": param_name,
                    "value": str(param_value),
                    "expected": f"Numeric ({rule['type']})",
                    "severity": "error",
                })

    checked = valid + invalid
    score = (valid / checked * 100) if checked > 0 else 100.0
    return {
        "total_params_checked": total,
        "valid": valid,
        "invalid": invalid,
        "unknown": unknown,
        "issues": issues,
        "score": round(score, 1),
    }


# ── Flow Statistics & Analytics ──

def get_flow_statistics(flow):
    """Compute comprehensive statistics about a processing flow.

    Returns: {
        "step_count": N,
        "total_parameters": N,
        "avg_params_per_step": float,
        "steps_with_descriptions": N,
        "steps_without_descriptions": N,
        "completeness_score": float,  # 0-100 based on descriptions and params present
        "data_type": str,
        "software": str,
        "has_metadata": bool,  # project, client, vessel all filled
        "parameter_types": {"filter": N, "velocity": N, "output": N, ...},  # categorize params
    }
    """
    step_count = len(flow.steps)
    total_parameters = sum(len(s.parameters) for s in flow.steps)
    avg_params = (total_parameters / step_count) if step_count > 0 else 0.0
    steps_with_desc = sum(1 for s in flow.steps if s.description)
    steps_without_desc = step_count - steps_with_desc

    # Completeness score: based on descriptions and parameter counts
    if step_count == 0:
        completeness_score = 0.0
    else:
        desc_ratio = steps_with_desc / step_count
        param_ratio = min(avg_params / 2.0, 1.0)  # normalize: 2+ params per step = 100%
        completeness_score = round((desc_ratio * 50 + param_ratio * 50), 1)

    has_metadata = bool(flow.project_name and flow.client and flow.vessel)

    # Categorize parameters by keyword
    param_categories = {
        "filter": 0, "velocity": 0, "output": 0, "input": 0,
        "correction": 0, "other": 0,
    }
    filter_keywords = ["filter", "freq", "cut", "band", "pass"]
    velocity_keywords = ["velocity", "nmo", "moveout", "cdp"]
    output_keywords = ["output", "export", "format", "sample"]
    input_keywords = ["input", "import", "load", "byte", "channel"]
    correction_keywords = ["correction", "tide", "svp", "heave", "diurnal", "igrf"]

    for step in flow.steps:
        for param_name in step.parameters:
            pn_lower = param_name.lower()
            categorized = False
            for kw in filter_keywords:
                if kw in pn_lower:
                    param_categories["filter"] += 1
                    categorized = True
                    break
            if not categorized:
                for kw in velocity_keywords:
                    if kw in pn_lower:
                        param_categories["velocity"] += 1
                        categorized = True
                        break
            if not categorized:
                for kw in output_keywords:
                    if kw in pn_lower:
                        param_categories["output"] += 1
                        categorized = True
                        break
            if not categorized:
                for kw in input_keywords:
                    if kw in pn_lower:
                        param_categories["input"] += 1
                        categorized = True
                        break
            if not categorized:
                for kw in correction_keywords:
                    if kw in pn_lower:
                        param_categories["correction"] += 1
                        categorized = True
                        break
            if not categorized:
                param_categories["other"] += 1

    return {
        "step_count": step_count,
        "total_parameters": total_parameters,
        "avg_params_per_step": round(avg_params, 2),
        "steps_with_descriptions": steps_with_desc,
        "steps_without_descriptions": steps_without_desc,
        "completeness_score": completeness_score,
        "data_type": flow.data_type,
        "software": flow.software,
        "has_metadata": has_metadata,
        "parameter_types": param_categories,
    }


def compare_flow_statistics(flows):
    """Compare statistics across multiple flows.

    Input: list of ProcessingFlow objects
    Returns: {
        "flow_count": N,
        "comparison": [
            {"data_type": str, "step_count": N, "total_parameters": N, "completeness_score": float}
        ],
        "avg_step_count": float,
        "avg_completeness": float,
        "most_detailed": str,  # data_type with highest completeness
        "least_detailed": str,
    }
    """
    comparison = []
    for flow in flows:
        stats = get_flow_statistics(flow)
        comparison.append({
            "data_type": stats["data_type"],
            "step_count": stats["step_count"],
            "total_parameters": stats["total_parameters"],
            "completeness_score": stats["completeness_score"],
        })

    flow_count = len(flows)
    avg_step_count = round(
        sum(c["step_count"] for c in comparison) / flow_count, 2
    ) if flow_count > 0 else 0.0
    avg_completeness = round(
        sum(c["completeness_score"] for c in comparison) / flow_count, 2
    ) if flow_count > 0 else 0.0

    most_detailed = ""
    least_detailed = ""
    if comparison:
        sorted_by_score = sorted(comparison, key=lambda c: c["completeness_score"])
        most_detailed = sorted_by_score[-1]["data_type"]
        least_detailed = sorted_by_score[0]["data_type"]

    return {
        "flow_count": flow_count,
        "comparison": comparison,
        "avg_step_count": avg_step_count,
        "avg_completeness": avg_completeness,
        "most_detailed": most_detailed,
        "least_detailed": least_detailed,
    }


# ── Export to Multiple Formats ──

def generate_excel_report(flow, output_path):
    """Generate Excel workbook from a processing flow.

    Sheet 1 'Overview': Project info table (metadata)
    Sheet 2 'Processing Steps': order, name, description, all parameters as columns
    Sheet 3 'Validation': parameter validation results
    Returns output path.
    """
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment

    wb = openpyxl.Workbook()

    # ── Sheet 1: Overview ──
    ws1 = wb.active
    ws1.title = "Overview"
    header_font = Font(bold=True, size=12)
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_font_white = Font(bold=True, size=12, color="FFFFFF")

    ws1.append(["Field", "Value"])
    for cell in ws1[1]:
        cell.font = header_font_white
        cell.fill = header_fill

    info_rows = [
        ("Project Name", flow.project_name or "TBD"),
        ("Client", flow.client or "TBD"),
        ("Data Type", flow.data_type or "TBD"),
        ("Vessel", flow.vessel or "TBD"),
        ("Survey Area", flow.area or "TBD"),
        ("Software", f"{flow.software} {flow.software_version}".strip()),
        ("Number of Lines", str(flow.line_count) if flow.line_count else "TBD"),
        ("Report Date", datetime.now().strftime("%Y-%m-%d")),
        ("Total Steps", str(len(flow.steps))),
    ]
    for key, val in info_rows:
        ws1.append([key, val])

    ws1.column_dimensions["A"].width = 20
    ws1.column_dimensions["B"].width = 40

    # ── Sheet 2: Processing Steps ──
    ws2 = wb.create_sheet("Processing Steps")

    # Collect all unique parameter names across all steps
    all_param_names = []
    for step in flow.steps:
        for pn in step.parameters:
            if pn not in all_param_names:
                all_param_names.append(pn)

    headers = ["Order", "Name", "Description"] + all_param_names
    ws2.append(headers)
    for cell in ws2[1]:
        cell.font = header_font_white
        cell.fill = header_fill

    for step in flow.steps:
        row = [step.order, step.name, step.description]
        for pn in all_param_names:
            row.append(str(step.parameters.get(pn, "")))
        ws2.append(row)

    ws2.column_dimensions["A"].width = 8
    ws2.column_dimensions["B"].width = 25
    ws2.column_dimensions["C"].width = 40

    # ── Sheet 3: Validation ──
    ws3 = wb.create_sheet("Validation")
    validation = validate_flow_parameters(flow)

    ws3.append(["Validation Summary"])
    ws3["A1"].font = Font(bold=True, size=14)
    ws3.append(["Total Parameters Checked", validation["total_params_checked"]])
    ws3.append(["Valid", validation["valid"]])
    ws3.append(["Invalid", validation["invalid"]])
    ws3.append(["Unknown", validation["unknown"]])
    ws3.append(["Score", f"{validation['score']}%"])
    ws3.append([])

    if validation["issues"]:
        ws3.append(["Step", "Parameter", "Value", "Expected", "Severity"])
        for cell in ws3[ws3.max_row]:
            cell.font = header_font_white
            cell.fill = header_fill
        for issue in validation["issues"]:
            ws3.append([
                issue["step"], issue["parameter"],
                issue["value"], issue["expected"], issue["severity"],
            ])

    ws3.column_dimensions["A"].width = 25
    ws3.column_dimensions["B"].width = 20
    ws3.column_dimensions["C"].width = 15
    ws3.column_dimensions["D"].width = 30
    ws3.column_dimensions["E"].width = 12

    wb.save(output_path)
    return output_path


def generate_json_export(flow):
    """Export flow as formatted JSON string.

    Returns: JSON string with proper formatting.
    """
    data = {
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
        "step_count": len(flow.steps),
        "steps": [
            {
                "order": s.order,
                "name": s.name,
                "description": s.description,
                "parameters": dict(s.parameters),
            }
            for s in flow.steps
        ],
    }
    return json.dumps(data, indent=2, ensure_ascii=False)


def generate_html_report(flow):
    """Generate standalone HTML report (for email/sharing).

    Returns: HTML string with embedded CSS styling.
    Contains: project info table, step cards, parameter tables.
    """
    steps_html = ""
    for step in flow.steps:
        params_html = ""
        if step.parameters:
            param_rows = ""
            for k, v in step.parameters.items():
                param_rows += f"<tr><td>{html.escape(k)}</td><td>{html.escape(str(v))}</td></tr>\n"
            params_html = f"""
            <table class="param-table">
                <tr><th>Parameter</th><th>Value</th></tr>
                {param_rows}
            </table>"""

        steps_html += f"""
        <div class="step-card">
            <h3>Step {step.order}: {html.escape(step.name)}</h3>
            <p class="step-desc">{html.escape(step.description or '')}</p>
            {params_html}
        </div>"""

    esc = html.escape
    html_output = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Processing Report - {esc(flow.data_type or '')}</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; color: #333; }}
        .container {{ max-width: 900px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
        h2 {{ color: #2c3e50; margin-top: 30px; }}
        .info-table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
        .info-table td {{ padding: 8px 12px; border: 1px solid #ddd; }}
        .info-table td:first-child {{ font-weight: bold; background: #f8f9fa; width: 180px; }}
        .step-card {{ background: #f8f9fa; border-left: 4px solid #3498db; padding: 15px; margin: 15px 0; border-radius: 0 4px 4px 0; }}
        .step-card h3 {{ margin-top: 0; color: #2c3e50; }}
        .step-desc {{ color: #555; font-style: italic; }}
        .param-table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
        .param-table th {{ background: #3498db; color: white; padding: 6px 10px; text-align: left; }}
        .param-table td {{ padding: 6px 10px; border: 1px solid #ddd; }}
        .footer {{ text-align: center; margin-top: 30px; color: #888; font-size: 0.9em; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Data Processing Report</h1>
        <h2>Project Information</h2>
        <table class="info-table">
            <tr><td>Project Name</td><td>{esc(flow.project_name or 'TBD')}</td></tr>
            <tr><td>Client</td><td>{esc(flow.client or 'TBD')}</td></tr>
            <tr><td>Data Type</td><td>{esc(flow.data_type or 'TBD')}</td></tr>
            <tr><td>Vessel</td><td>{esc(flow.vessel or 'TBD')}</td></tr>
            <tr><td>Survey Area</td><td>{esc(flow.area or 'TBD')}</td></tr>
            <tr><td>Software</td><td>{esc(flow.software or '')} {esc(flow.software_version or '')}</td></tr>
            <tr><td>Number of Lines</td><td>{esc(str(flow.line_count) if flow.line_count else 'TBD')}</td></tr>
            <tr><td>Report Date</td><td>{datetime.now().strftime('%Y-%m-%d')}</td></tr>
        </table>

        <h2>Processing Flow ({len(flow.steps)} steps)</h2>
        {steps_html}

        <div class="footer">
            <p>Generated by ProcessingReportDraft</p>
        </div>
    </div>
</body>
</html>"""
    return html_output


# ── Bulk Template Operations ──

def generate_all_templates(project_name="", client="", vessel="", area=""):
    """Generate templates for ALL data types at once with common metadata.

    Returns: {
        "SBP": ProcessingFlow,
        "UHR": ProcessingFlow,
        "MBES": ProcessingFlow,
        "MAG": ProcessingFlow,
        "SSS": ProcessingFlow,
    }
    """
    result = {}
    for dt in ["SBP", "UHR", "MBES", "MAG", "SSS"]:
        flow = generate_flow_from_template(dt)
        flow.project_name = project_name
        flow.client = client
        flow.vessel = vessel
        flow.area = area
        result[dt] = flow
    return result


def generate_bulk_docx(flows, output_dir):
    """Generate DOCX reports for multiple flows.

    Input: {data_type: ProcessingFlow, ...}
    Writes files to output_dir as Processing_Report_{data_type}.docx
    Returns: list of output file paths.
    """
    os.makedirs(output_dir, exist_ok=True)
    output_paths = []
    for data_type, flow in flows.items():
        filename = f"Processing_Report_{data_type}.docx"
        output_path = os.path.join(output_dir, filename)
        generate_docx_report(flow, output_path)
        output_paths.append(output_path)
    return output_paths
