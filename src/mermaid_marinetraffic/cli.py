"""Top-level command dispatcher for mermaid-marinetraffic."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from . import __version__
from . import winnow_gps


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level command parser."""
    parser = argparse.ArgumentParser(
        prog="mermaid-marinetraffic",
        description="Prepare MERMAID position histories for MarineTraffic.",
    )
    parser.add_argument("-v", "--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", metavar="command")
    winnow_gps.add_parser(commands)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    """Run the requested mermaid-marinetraffic command."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "handler"):
        parser.error("a command is required")
    args.handler(args)
