# Bathymetrix®
# https://bathymetrix.com
# © 2026 Bathymetrix, LLC
# Author: Joel D. Simon <jdsimon@bathymetrix.com>
# SPDX-License-Identifier: MIT

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
        description="Prepare MERMAID GPS trajectories for MarineTraffic.",
    )
    parser.add_argument("-v", "--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", metavar="command")
    winnow_gps.add_parsers(commands)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    """Run the requested mermaid-marinetraffic command."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "handler"):
        parser.error("a command is required")
    if getattr(args, "between", None) is not None and args.between[0] > args.between[1]:
        parser.error("--between START must be earlier than or equal to END")
    if (getattr(args, "from_start", None) is not None or getattr(args, "to_end", None) is not None) and getattr(args, "npts", None) is None:
        parser.error("--from and --to require -n/--npts")
    args.handler(args)
