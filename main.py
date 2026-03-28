"""ProcessingReportDraft - Processing Log to Report Draft Generator.

Usage:
    python main.py                              -- Start web GUI (default, port 5404)
    python main.py --port 5408                  -- Start web GUI on custom port
    python main.py web --port 5404              -- Start web GUI explicitly
    python main.py cli template --type SBP      -- CLI: generate from template
    python main.py cli parse processing.log     -- CLI: parse log file
"""
import os
import sys

import click

sys.path.insert(0, os.path.dirname(__file__))
from core import (
    parse_processing_log, generate_docx_report, generate_flow_from_template,
    generate_text_report, get_supported_types, ProcessingFlow,
)


@click.group(invoke_without_command=True)
@click.option("--port", default=5404, type=int, help="Web server port (default: 5404)")
@click.pass_context
def main(ctx, port):
    """ProcessingReportDraft - Generate processing report drafts.

    Run without arguments to start the web GUI.
    Use 'cli' subcommand for command-line mode.
    """
    ctx.ensure_object(dict)
    ctx.obj["port"] = port
    if ctx.invoked_subcommand is None:
        # Default: start web GUI
        _start_web(port)


@main.command("web")
@click.option("--port", default=5404, type=int, help="Web server port (default: 5404)")
def web_cmd(port):
    """Start the web GUI server."""
    _start_web(port)


def _start_web(port):
    """Internal helper to start the web server."""
    from app import run_server
    run_server(port=port)


@main.group("cli")
def cli():
    """Command-line interface for report generation."""
    pass


SOFTWARE_MAP = {
    "SBP": "RadExPro",
    "UHR": "RadExPro",
    "MBES": "CARIS HIPS and SIPS",
    "MAG": "Oasis Montaj",
    "SSS": "SonarWiz / CARIS",
}

ALL_TYPES = ["SBP", "UHR", "MBES", "MAG", "SSS"]


@cli.command("template")
@click.option("--type", "data_type", default="SBP",
              type=click.Choice(ALL_TYPES, case_sensitive=False),
              help="Data type (SBP, UHR, MBES, MAG, SSS)")
@click.option("--project", default="", help="Project name")
@click.option("--client", default="", help="Client name")
@click.option("--vessel", default="", help="Vessel name")
@click.option("--area", default="", help="Survey area")
@click.option("--software", default=None, help="Processing software (auto-detected from data type)")
@click.option("--lines", default=0, type=int, help="Number of lines")
@click.option("--output", "-o", type=click.Path(), default=None, help="Output DOCX path")
@click.option("--text", "text_output", type=click.Path(), default=None, help="Also save text report")
def template(data_type, project, client, vessel, area, software, lines, output, text_output):
    """Generate a report draft from a standard template."""
    data_type = data_type.upper()
    flow = generate_flow_from_template(data_type)
    flow.project_name = project
    flow.client = client
    flow.vessel = vessel
    flow.area = area
    flow.software = software or SOFTWARE_MAP.get(data_type, "RadExPro")
    flow.line_count = lines

    if output is None:
        output = f"Processing_Report_Draft_{data_type}.docx"

    generate_docx_report(flow, output)
    click.echo(f"Report draft generated: {output}")
    click.echo(f"  Data type: {data_type}")
    click.echo(f"  Steps: {flow.step_count}")
    click.echo(f"  Software: {flow.software}")
    click.echo(f"  Project: {project or 'TBD'}")

    if text_output:
        text = generate_text_report(flow)
        with open(text_output, "w", encoding="utf-8") as f:
            f.write(text)
        click.echo(f"  Text report: {text_output}")


@cli.command("list-types")
def list_types():
    """List all supported data types and their processing steps."""
    supported = get_supported_types()
    click.echo("Supported data types:")
    click.echo("=" * 50)
    for dt, info in supported.items():
        sw = SOFTWARE_MAP.get(dt, "RadExPro")
        click.echo(f"\n  {dt}")
        click.echo(f"    Software: {sw}")
        click.echo(f"    Steps: {info['step_count']}")
        for i, step_name in enumerate(info.get("steps_preview", []), 1):
            click.echo(f"      {i}. {step_name}")
        if info["step_count"] > 5:
            click.echo(f"      ... (+{info['step_count'] - 5} more)")


@cli.command("parse")
@click.argument("logfile", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), default=None, help="Output DOCX path")
@click.option("--show", is_flag=True, help="Show parsed flow instead of generating report")
def parse(logfile, output, show):
    """Parse a processing log file and generate a report."""
    with open(logfile, "r", encoding="utf-8-sig") as f:
        text = f.read()

    flow = parse_processing_log(text)

    if show:
        click.echo(f"Project: {flow.project_name}")
        click.echo(f"Client: {flow.client}")
        click.echo(f"Type: {flow.data_type}")
        click.echo(f"Software: {flow.software}")
        click.echo(f"Steps: {flow.step_count}")
        click.echo()
        for step in flow.steps:
            click.echo(f"  {step.order}. {step.name}")
            if step.description:
                click.echo(f"     {step.description}")
            for k, v in step.parameters.items():
                click.echo(f"     {k}: {v}")
        return

    if output is None:
        base = os.path.splitext(os.path.basename(logfile))[0]
        output = f"{base}_Report_Draft.docx"

    generate_docx_report(flow, output)
    click.echo(f"Report draft generated: {output}")
    click.echo(f"  Parsed {flow.step_count} processing steps")


if __name__ == "__main__":
    main()
