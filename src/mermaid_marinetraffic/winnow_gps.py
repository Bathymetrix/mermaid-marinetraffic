"""Prepare MERMAID GPS trajectories and individual-point KML products."""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

KML_NS = "http://www.opengis.net/kml/2.2"
GX_NS = "http://www.google.com/kml/ext/2.2"
NS = {"k": KML_NS}
DEFAULT_OUTPUT_ENVIRONMENT_VARIABLE = "MERMAID"
DEFAULT_OUTPUT_SUBDIRECTORY = "marinetraffic"
MARINETRAFFIC_MAX_KML_BYTES = 400_000


@dataclass(frozen=True)
class PositionRecord:
    """One validated GPS fix, independent of its input source."""

    timestamp: datetime
    latitude: str
    longitude: str

    @property
    def lat_lon(self) -> tuple[str, str]:
        return self.latitude, self.longitude

    @property
    def kml_coordinate(self) -> str:
        return f"{self.longitude},{self.latitude},0"


class KMLSizeError(RuntimeError):
    """Raised when a rendered product exceeds MarineTraffic's file-size limit."""


class GPSKMLWinnower:
    def __init__(self, limit: int | None = None, max_kml_bytes: int = MARINETRAFFIC_MAX_KML_BYTES) -> None:
        self.limit = limit
        self.max_kml_bytes = max_kml_bytes
        ET.register_namespace("", KML_NS)
        ET.register_namespace("gx", GX_NS)

    @staticmethod
    def build_default_output_filename(station: str, source_tag: str, product: str) -> str:
        return f"gps_{product}_{station}_src-{source_tag}.kml"

    @staticmethod
    def format_output_datetime(dt: datetime) -> str:
        return dt.strftime("%d-%b-%Y %H:%M")

    @staticmethod
    def extract_station_code(document_name: str) -> str:
        if "-" not in document_name:
            raise ValueError(f"Document name missing '-': {document_name!r}")
        alnum = "".join(ch for ch in document_name.split("-", 1)[1] if ch.isalnum())
        if len(alnum) < 2:
            raise ValueError(f"Cannot derive station code from: {document_name!r}")
        return f"{alnum[0]}{'0' * max(0, 5 - len(alnum))}{alnum[1:-1][-3:]}{alnum[-1]}"

    @staticmethod
    def parse_point_datetime(name_text: str) -> datetime:
        text = name_text.strip()
        if len(text) >= 8 and text[2] == "/" and text[5] == "/":
            return datetime.strptime(text, "%d/%m/%y %H:%M")
        if len(text) >= 10 and text[4] == "-" and text[7] == "-":
            return datetime.strptime(text, "%Y-%m-%d %H:%M")
        raise ValueError(f"Unrecognized datetime format: {name_text!r}")

    @staticmethod
    def parse_eso_datetime(text: str) -> datetime:
        return datetime.strptime(text.strip(), "%d-%b-%Y %H:%M:%S")

    @staticmethod
    def parse_record_datetime(text: str) -> datetime:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None)

    @staticmethod
    def parse_vit_datetime(text: str) -> datetime:
        return datetime.strptime(text, "%Y%m%d-%Hh%Mmn%S")

    @staticmethod
    def parse_lat_lon(coords_text: str) -> tuple[str, str]:
        parts = [part.strip() for part in coords_text.strip().split(",")]
        if len(parts) < 2:
            raise ValueError(f"Invalid coordinates text: {coords_text!r}")
        return parts[1], parts[0]

    @staticmethod
    def parse_degrees_minutes(text: str) -> str:
        match = re.fullmatch(r"\s*([NSEW])(\d+)deg(\d+(?:\.\d+)?)mn\s*", text)
        if match is None:
            raise ValueError(f"Invalid degrees/minutes coordinate: {text!r}")
        direction, degrees, minutes = match.groups()
        value = int(degrees) + float(minutes) / 60
        return f"{-value if direction in {'S', 'W'} else value:.6f}"

    @staticmethod
    def get_text(el: ET.Element | None) -> str:
        return (el.text or "").strip() if el is not None and el.text is not None else ""

    @staticmethod
    def default_output_directory() -> Path:
        mermaid_root = os.environ.get(DEFAULT_OUTPUT_ENVIRONMENT_VARIABLE)
        if not mermaid_root:
            raise RuntimeError("Set MERMAID or provide -o/--output to choose an output location.")
        return Path(mermaid_root) / DEFAULT_OUTPUT_SUBDIRECTORY

    @staticmethod
    def resolve_output_path(output_path: Path, station: str, source_tag: str, product: str) -> Path:
        filename = GPSKMLWinnower.build_default_output_filename(station, source_tag, product)
        if output_path.exists() and output_path.is_dir():
            return output_path / filename
        if output_path.suffix.lower() == ".kml":
            output_path.parent.mkdir(parents=True, exist_ok=True)
            return output_path
        output_path.mkdir(parents=True, exist_ok=True)
        return output_path / filename

    def ordered_unique_records(self, records: list[PositionRecord]) -> list[PositionRecord]:
        """Remove adjacent exact duplicates and return chronological GPS fixes."""
        deduped: list[PositionRecord] = []
        previous_key: tuple[datetime, tuple[str, str]] | None = None
        for record in records:
            key = record.timestamp, record.lat_lon
            if key != previous_key:
                deduped.append(record)
            previous_key = key
        return sorted(deduped, key=lambda record: record.timestamp)

    def select_records(self, records: list[PositionRecord]) -> list[PositionRecord]:
        """Retain the configured number of most-recent unique GPS fixes."""
        ordered = self.ordered_unique_records(records)
        return ordered if self.limit is None else ordered[-self.limit:]

    def parse_kml(self, input_path: Path) -> tuple[str, list[PositionRecord]]:
        root = ET.parse(input_path).getroot()
        document = root.find("k:Document", NS)
        if document is None:
            raise RuntimeError("No <Document> found")
        document_name = self.get_text(document.find("k:name", NS))
        gps_folder = document.find("k:Folder[@id='GPS points']", NS)
        if not document_name or gps_folder is None:
            raise RuntimeError("KML lacks document name or GPS points folder")
        records: list[PositionRecord] = []
        for placemark in gps_folder.findall("k:Placemark", NS):
            name = self.get_text(placemark.find("k:name", NS))
            coordinates = self.get_text(placemark.find(".//k:Point/k:coordinates", NS))
            if name and coordinates:
                latitude, longitude = self.parse_lat_lon(coordinates)
                records.append(PositionRecord(self.parse_point_datetime(name), latitude, longitude))
        return self.extract_station_code(document_name), records

    def parse_eso(self, input_path: Path) -> tuple[str, list[PositionRecord]]:
        station: str | None = None
        records: list[PositionRecord] = []
        for raw_line in input_path.read_text(encoding="utf-8").splitlines():
            parts = raw_line.split()
            if not parts:
                continue
            if len(parts) < 5:
                raise ValueError(f"Invalid EarthScope-Oceans row: {raw_line!r}")
            if station is not None and parts[0] != station:
                raise ValueError("EarthScope-Oceans file contains multiple stations")
            station = parts[0]
            records.append(PositionRecord(self.parse_eso_datetime(f"{parts[1]} {parts[2]}"), parts[3], parts[4]))
        if station is None:
            raise RuntimeError("No EarthScope-Oceans records found")
        return station, records

    def parse_jsonl(self, input_path: Path) -> tuple[str, list[PositionRecord]]:
        station: str | None = None
        records: list[PositionRecord] = []
        for line_number, raw_line in enumerate(input_path.read_text(encoding="utf-8").splitlines(), 1):
            if not raw_line.strip():
                continue
            entry = json.loads(raw_line)
            if entry.get("gps_record_kind") != "fix_position":
                continue
            raw_values = entry.get("raw_values")
            serial, instrument_id = entry.get("instrument_serial"), entry.get("instrument_id")
            if not isinstance(raw_values, dict) or not isinstance(serial, str) or not isinstance(instrument_id, str):
                raise ValueError(f"JSONL line {line_number} lacks GPS position or instrument identity")
            serial_station = self.extract_station_code(serial)
            match = re.fullmatch(r"([A-Z])(\d+)", instrument_id)
            if match is None:
                raise ValueError(f"Invalid instrument_id on JSONL line {line_number}: {instrument_id!r}")
            id_station = f"{match.group(1)}{int(match.group(2)):04d}"
            if serial_station != id_station:
                raise ValueError(f"Instrument identity mismatch on JSONL line {line_number}")
            if station is not None and station != id_station:
                raise ValueError("mermaid-records JSONL contains multiple stations")
            station = id_station
            records.append(PositionRecord(self.parse_record_datetime(entry["record_time"]), self.parse_degrees_minutes(raw_values["latitude"]), self.parse_degrees_minutes(raw_values["longitude"])))
        if station is None:
            raise RuntimeError("No fix_position records found")
        return station, records

    def parse_vit(self, input_path: Path) -> tuple[str, list[PositionRecord]]:
        serial_id = input_path.stem
        station_match = re.fullmatch(r"([A-Z])(\d+)", serial_id)
        station = (
            f"{station_match.group(1)}{int(station_match.group(2)):04d}"
            if station_match is not None
            else self.extract_station_code(serial_id)
        )
        position_line = re.compile(
            r"^(\d{8}-\d{2}h\d{2}mn\d{2}):\s*"
            r"([NS]\d+deg\d+(?:\.\d+)?mn),\s*"
            r"([EW]\d+deg\d+(?:\.\d+)?mn)$"
        )
        records: list[PositionRecord] = []
        for raw_line in input_path.read_text(encoding="utf-8").splitlines():
            match = position_line.fullmatch(raw_line.strip())
            if match is None:
                continue
            timestamp, latitude, longitude = match.groups()
            records.append(
                PositionRecord(
                    self.parse_vit_datetime(timestamp),
                    self.parse_degrees_minutes(latitude),
                    self.parse_degrees_minutes(longitude),
                )
            )
        if not records:
            raise RuntimeError(f"No GPS position lines found in {input_path}")
        return station, records

    def parse_source(self, input_path: Path, source_type: str) -> tuple[str, list[PositionRecord]]:
        return {
            "automaid": self.parse_kml,
            "earthscopeoceans": self.parse_eso,
            "mermaid-records": self.parse_jsonl,
            "vit": self.parse_vit,
        }[source_type](input_path)

    @staticmethod
    def add_styles(document: ET.Element) -> None:
        trajectory_style = ET.SubElement(document, f"{{{KML_NS}}}Style", {"id": "trajectory"})
        line_style = ET.SubElement(trajectory_style, f"{{{KML_NS}}}LineStyle")
        ET.SubElement(line_style, f"{{{KML_NS}}}color").text = "ffcc6600"
        ET.SubElement(line_style, f"{{{KML_NS}}}width").text = "3"
        latest_style = ET.SubElement(document, f"{{{KML_NS}}}Style", {"id": "latest-position"})
        icon_style = ET.SubElement(latest_style, f"{{{KML_NS}}}IconStyle")
        ET.SubElement(icon_style, f"{{{KML_NS}}}color").text = "ff00ffff"
        ET.SubElement(icon_style, f"{{{KML_NS}}}scale").text = "1.8"
        points_style = ET.SubElement(document, f"{{{KML_NS}}}Style", {"id": "gps-point"})
        ET.SubElement(ET.SubElement(points_style, f"{{{KML_NS}}}IconStyle"), f"{{{KML_NS}}}scale").text = "1"

    def render_kml_bytes(self, records: list[PositionRecord], station: str, source_type: str, source_ref: str, product: str, generated_utc: str) -> bytes:
        root = ET.Element(f"{{{KML_NS}}}kml")
        document = ET.SubElement(root, f"{{{KML_NS}}}Document")
        ET.SubElement(document, f"{{{KML_NS}}}name").text = f"{station} {product}"
        ET.SubElement(document, f"{{{KML_NS}}}description").text = f"Generated from {source_type} input"
        self.add_styles(document)
        extended_data = ET.SubElement(document, f"{{{KML_NS}}}ExtendedData")
        metadata = {
            "source_type": source_type,
            "source_ref": source_ref,
            "generated_utc": generated_utc,
            "geometry_type": product,
            "gps_points": str(len(records)),
            "limit": "all" if self.limit is None else str(self.limit),
        }
        for key, value in metadata.items():
            data = ET.SubElement(extended_data, f"{{{KML_NS}}}Data", {"name": key})
            ET.SubElement(data, f"{{{KML_NS}}}value").text = value

        if product == "trajectory":
            if len(records) >= 2:
                trajectory = ET.SubElement(document, f"{{{KML_NS}}}Placemark")
                ET.SubElement(trajectory, f"{{{KML_NS}}}name").text = f"{station} trajectory"
                ET.SubElement(trajectory, f"{{{KML_NS}}}styleUrl").text = "#trajectory"
                line = ET.SubElement(trajectory, f"{{{KML_NS}}}LineString")
                ET.SubElement(line, f"{{{KML_NS}}}coordinates").text = "\n".join(record.kml_coordinate for record in records)
            if records:
                latest = records[-1]
                placemark = ET.SubElement(document, f"{{{KML_NS}}}Placemark")
                ET.SubElement(placemark, f"{{{KML_NS}}}name").text = f"{station} - latest - {self.format_output_datetime(latest.timestamp)}"
                ET.SubElement(placemark, f"{{{KML_NS}}}styleUrl").text = "#latest-position"
                point = ET.SubElement(placemark, f"{{{KML_NS}}}Point")
                ET.SubElement(point, f"{{{KML_NS}}}coordinates").text = latest.kml_coordinate
        else:
            for record in records:
                placemark = ET.SubElement(document, f"{{{KML_NS}}}Placemark")
                ET.SubElement(placemark, f"{{{KML_NS}}}name").text = f"{station} - {self.format_output_datetime(record.timestamp)}"
                ET.SubElement(placemark, f"{{{KML_NS}}}styleUrl").text = "#gps-point"
                point = ET.SubElement(placemark, f"{{{KML_NS}}}Point")
                ET.SubElement(point, f"{{{KML_NS}}}coordinates").text = record.kml_coordinate

        ET.indent(root, space="    ")
        return ET.tostring(root, encoding="UTF-8", xml_declaration=True)

    def maximum_fitting_limit(self, all_records: list[PositionRecord], station: str, source_type: str, source_ref: str, product: str, generated_utc: str) -> int:
        low, high, best = 1, len(all_records), 0
        while low <= high:
            candidate = (low + high) // 2
            data = self.render_kml_bytes(all_records[-candidate:], station, source_type, source_ref, product, generated_utc)
            if len(data) <= self.max_kml_bytes:
                best = candidate
                low = candidate + 1
            else:
                high = candidate - 1
        return best

    def enforce_size(self, data: bytes, all_records: list[PositionRecord], station: str, source_type: str, source_ref: str, product: str, generated_utc: str) -> None:
        if len(data) <= self.max_kml_bytes:
            return
        maximum = self.maximum_fitting_limit(all_records, station, source_type, source_ref, product, generated_utc)
        product_name = "Trajectory" if product == "trajectory" else "Points"
        message = (
            f"{product_name} KML exceeds MarineTraffic's 400 KB file-size limit.\n\n"
            f"KML size:           {len(data)} bytes\n"
            f"Maximum size:       {self.max_kml_bytes} bytes\n"
            f"GPS points:         {len(self.select_records(all_records))}\n"
            f"Maximum GPS points: {maximum}"
        )
        if maximum:
            message += f"\n\nRerun with --limit {maximum} or smaller."
        else:
            message += "\n\nEven one GPS fix cannot fit this KML representation."
        raise KMLSizeError(message)

    @staticmethod
    def write_bytes_atomically(output_path: Path, data: bytes) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=output_path.parent, delete=False) as temporary:
            temporary.write(data)
            temporary_path = Path(temporary.name)
        temporary_path.replace(output_path)

    def prepare_product(self, input_path: Path, source_type: str, source_tag: str, product: str, output_path: Path, generated_utc: str) -> tuple[Path, bytes]:
        station, parsed_records = self.parse_source(input_path, source_type)
        all_records = self.ordered_unique_records(parsed_records)
        selected_records = self.select_records(parsed_records)
        if not selected_records:
            raise RuntimeError(f"No valid GPS fixes found in {input_path}")
        final_output = self.resolve_output_path(output_path, station, source_tag, product)
        data = self.render_kml_bytes(selected_records, station, source_type, str(input_path), product, generated_utc)
        self.enforce_size(data, all_records, station, source_type, str(input_path), product, generated_utc)
        return final_output, data

    def process_paths(self, input_path: Path, output_path: Path, source_type: str, source_tag: str, product: str) -> list[Path]:
        patterns = {
            "automaid": "position.kml",
            "earthscopeoceans": "*_all.txt",
            "mermaid-records": "log_gps_records.*.jsonl",
            "vit": "*.vit",
        }
        is_directory = input_path.is_dir()
        if is_directory:
            if output_path.suffix.lower() == ".kml":
                raise RuntimeError("Directory input requires -o to be a directory, not a .kml file.")
            inputs = sorted(input_path.rglob(patterns[source_type]))
            if not inputs:
                raise RuntimeError(f"No matching {source_type} files under {input_path}")
        elif input_path.is_file():
            inputs = [input_path]
        else:
            raise RuntimeError(f"Not a file or directory: {input_path}")

        generated_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        prepared = [
            self.prepare_product(path, source_type, source_tag, product, output_path, generated_utc)
            for path in inputs
        ]
        output_paths = [path for path, _ in prepared]
        if len(output_paths) != len(set(output_paths)):
            raise RuntimeError("Multiple inputs would write the same flat output filename.")
        for final_output, data in prepared:
            self.write_bytes_atomically(final_output, data)
            print(f"Output: {final_output} ({len(data)} bytes)")
        return output_paths


def positive_limit(value: str) -> int:
    limit = int(value)
    if limit <= 0:
        raise argparse.ArgumentTypeError("--limit must be a positive number of GPS fixes")
    return limit


def add_parsers(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    for product, help_text in (
        ("trajectory", "Write trajectory KML with latest position."),
        ("points", "Write KML containing individual GPS Point features."),
    ):
        parser = subparsers.add_parser(product, help=help_text)
        configure_parser(parser)
        parser.set_defaults(handler=run, product=product)


def configure_parser(parser: argparse.ArgumentParser) -> None:
    sources = parser.add_mutually_exclusive_group(required=True)
    sources.add_argument("--vit", type=Path, metavar="PATH", help="preferred MERMAID .vit file or directory")
    sources.add_argument("--kml", type=Path, metavar="PATH", help="automaid position.kml file or directory")
    sources.add_argument("--eso", type=Path, metavar="PATH", help="ESO (EarthScope-Oceans) local file or directory")
    sources.add_argument("--jsonl", type=Path, metavar="PATH", help="mermaid-records GPS JSONL file or directory")
    parser.add_argument("-o", "--output", type=Path, help="Output file or directory (default: $MERMAID/marinetraffic)")
    parser.add_argument("--limit", type=positive_limit, metavar="N", help="Use only the N most recent unique GPS fixes (default: all available fixes).")


def selected_source(args: argparse.Namespace) -> tuple[Path, str, str]:
    for input_path, source_type, source_tag in (
        (args.vit, "vit", "vit"),
        (args.kml, "automaid", "kml"),
        (args.eso, "earthscopeoceans", "eso"),
        (args.jsonl, "mermaid-records", "jsonl"),
    ):
        if input_path is not None:
            return input_path, source_type, source_tag
    raise RuntimeError("No input source selected")


def run(args: argparse.Namespace) -> None:
    input_path, source_type, source_tag = selected_source(args)
    output_path = args.output or GPSKMLWinnower.default_output_directory()
    outputs = GPSKMLWinnower(limit=args.limit).process_paths(
        input_path, output_path, source_type, source_tag, args.product
    )
    if len(outputs) > 1:
        print(f"Processed {len(outputs)} files.")


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="mermaid-marinetraffic")
    subparsers = parser.add_subparsers(dest="command", required=True)
    add_parsers(subparsers)
    args = parser.parse_args(argv)
    args.handler(args)


if __name__ == "__main__":
    main()
