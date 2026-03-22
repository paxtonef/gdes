from __future__ import annotations
from pathlib import Path
import click
from src.gdes import cli

@click.command(name="health")
@click.option('--json', 'output_json', is_flag=True, help="Output raw JSON")
@click.option('--db', default=str(Path.home() / ".gdes" / "output" / "registry.db"), help="Database path")
def health_cmd(output_json, db):
    """Check graph integrity and operational health"""
    import json
    from dataclasses import asdict
    from src.health.integrity import IntegrityChecker

    checker = IntegrityChecker(Path(db))
    report = checker.check()

    if output_json:
        click.echo(json.dumps(asdict(report), indent=2))
    else:
        click.echo(checker.format_report(report))

    if report.integrity_score < 0.7:
        raise click.Abort()

cli.add_command(health_cmd)

if __name__ == "__main__":
    cli()
