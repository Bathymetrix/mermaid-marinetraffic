# Bathymetrix®
# https://bathymetrix.com
# © 2026 Bathymetrix, LLC
# Author: Joel D. Simon <jdsimon@bathymetrix.com>
# SPDX-License-Identifier: MIT

"""MERMAID position-history tools for MarineTraffic."""

from importlib.resources import files

__version__ = files(__package__).joinpath("VERSION").read_text(encoding="utf-8").strip()
__author__ = "Joel D. Simon"
__license__ = "MIT"
__copyright__ = "© 2026 Bathymetrix, LLC"
