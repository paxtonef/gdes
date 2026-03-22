#!/usr/bin/env python3
"""
Start the GDES V2.0 REST API.
Usage:
    python run_api.py
    python run_api.py --port 8080
"""
import uvicorn
import click

@click.command()
@click.option("--host", default="127.0.0.1", help="Bind host")
@click.option("--port", default=8000, type=int, help="Bind port")
@click.option("--reload", is_flag=True, help="Auto-reload on file changes")
def main(host, port, reload):
    uvicorn.run("src.api:app", host=host, port=port, reload=reload)

if __name__ == "__main__":
    main()
