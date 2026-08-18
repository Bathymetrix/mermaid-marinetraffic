"""Winnow local MERMAID GPS position sources into import-ready KML."""

from __future__ import annotations

import argparse
import heapq
import json
import os
import re
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


@dataclass(frozen=True)
class PositionRecord:
    """One parsed GPS position, independent of its input source."""

    timestamp: datetime
    latitude: str
    longitude: str

    @property
    def lat_lon(self) -> tuple[str, str]:
        return self.latitude, self.longitude


class GPSKMLWinnower:
    def __init__(self, limit: int = 50) -> None:
        self.limit = limit
        ET.register_namespace("", KML_NS)
        ET.register_namespace("gx", GX_NS)

    @staticmethod
    def build_default_output_filename(station: str, source_tag: str) -> str:
        return f"recent_gps_{station}_src-{source_tag}.kml"

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
    def parse_som_datetime(text: str) -> datetime:
        return datetime.strptime(text.strip(), "%d-%b-%Y %H:%M:%S")

    @staticmethod
    def parse_record_datetime(text: str) -> datetime:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None)

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
    def resolve_output_path(output_path: Path, station: str, source_tag: str) -> Path:
        default_name = GPSKMLWinnower.build_default_output_filename(station, source_tag)
        if output_path.exists() and output_path.is_dir():
            return output_path / default_name
        if output_path.suffix.lower() == ".kml":
            output_path.parent.mkdir(parents=True, exist_ok=True)
            return output_path
        output_path.mkdir(parents=True, exist_ok=True)
        return output_path / default_name

    def select_recent_unique(self, records: list[PositionRecord]) -> list[PositionRecord]:
        deduped: list[PositionRecord] = []
        previous_key: tuple[datetime, tuple[str, str]] | None = None
        for record in records:
            key = record.timestamp, record.lat_lon
            if key != previous_key:
                deduped.append(record)
            previous_key = key
        return heapq.nlargest(self.limit, deduped, key=lambda record: record.timestamp)

    def parse_kml(self, input_path: Path) -> tuple[str, list[PositionRecord]]:
        root = ET.parse(input_path).getroot()
        document = root.find("k:Document", NS)
        if document is None:
            raise RuntimeError("No <Document> found")
        document_name = self.get_text(document.find("k:name", NS))
        gps_folder = document.find("k:Folder[@id='GPS points']", NS)
        if not document_name or gps_folder is None:
            raise RuntimeError("KML lacks document name or GPS points folder")
        records = []
        for placemark in gps_folder.findall("k:Placemark", NS):
            name = self.get_text(placemark.find("k:name", NS))
            coordinates = self.get_text(placemark.find(".//k:Point/k:coordinates", NS))
            if name and coordinates:
                latitude, longitude = self.parse_lat_lon(coordinates)
                records.append(PositionRecord(self.parse_point_datetime(name), latitude, longitude))
        return self.extract_station_code(document_name), records

    def parse_txt(self, input_path: Path) -> tuple[str, list[PositionRecord]]:
        station: str | None = None
        records: list[PositionRecord] = []
        for raw_line in input_path.read_text(encoding="utf-8").splitlines():
            parts = raw_line.split()
            if not parts:
                continue
            if len(parts) < 5:
                raise ValueError(f"Invalid EarthScopeOceans.org SOM row: {raw_line!r}")
            if station is not None and parts[0] != station:
                raise ValueError("EarthScopeOceans.org SOM file contains multiple stations")
            station = parts[0]
            records.append(PositionRecord(self.parse_som_datetime(f"{parts[1]} {parts[2]}"), parts[3], parts[4]))
        if station is None:
            raise RuntimeError("No EarthScopeOceans.org SOM records found")
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

    def write_records_to_kml(self, records: list[PositionRecord], station: str, output_path: Path, source_type: str, source_ref: str) -> None:
        root = ET.Element(f"{{{KML_NS}}}kml")
        document = ET.SubElement(root, f"{{{KML_NS}}}Document")
        ET.SubElement(document, f"{{{KML_NS}}}name").text = station
        ET.SubElement(document, f"{{{KML_NS}}}description").text = f"Generated from {source_type} input"
        extended_data = ET.SubElement(document, f"{{{KML_NS}}}ExtendedData")
        metadata = {"source_type": source_type, "source_ref": source_ref, "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "limit": str(self.limit)}
        for key, value in metadata.items():
            data = ET.SubElement(extended_data, f"{{{KML_NS}}}Data", {"name": key})
            ET.SubElement(data, f"{{{KML_NS}}}value").text = value
        folder = ET.SubElement(document, f"{{{KML_NS}}}Folder", {"id": "GPS points"})
        ET.SubElement(folder, f"{{{KML_NS}}}name").text = "GPS points"
        for record in records:
            placemark = ET.SubElement(folder, f"{{{KML_NS}}}Placemark")
            ET.SubElement(placemark, f"{{{KML_NS}}}name").text = f"{station} - {self.format_output_datetime(record.timestamp)}"
            ET.SubElement(placemark, f"{{{KML_NS}}}visibility").text = "1"
            ET.SubElement(placemark, f"{{{KML_NS}}}styleUrl").text = "#markerStyle2"
            point = ET.SubElement(placemark, f"{{{KML_NS}}}Point")
            ET.SubElement(point, f"{{{KML_NS}}}coordinates").text = f"{record.longitude},{record.latitude},0"
        ET.indent(root, space="    ")
        ET.ElementTree(root).write(output_path, encoding="UTF-8", xml_declaration=True)

    def process_file(
        self, input_path: Path, output_path: Path, source_type: str, source_tag: str
    ) -> Path:
        station, records = self.parse_source(input_path, source_type)
        selected = self.select_recent_unique(records)
        final_output = self.resolve_output_path(output_path, station, source_tag)
        self.write_records_to_kml(selected, station, final_output, source_type, str(input_path))
        print(f"Station code: {station}\nInput GPS records: {len(records)}\nWritten placemarks: {len(selected)}\nOutput: {final_output}")
        return final_output

    def parse_source(
        self, input_path: Path, source_type: str
    ) -> tuple[str, list[PositionRecord]]:
        parser = {
            "automaid": self.parse_kml,
            "earthscopeoceans": self.parse_txt,
            "mermaid-records": self.parse_jsonl,
        }[source_type]
        return parser(input_path)

    def process_directory(
        self, input_directory: Path, output_directory: Path, source_type: str, source_tag: str
    ) -> list[Path]:
        if not input_directory.is_dir():
            raise RuntimeError(f"Not a directory: {input_directory}")
        patterns = {
            "automaid": "position.kml",
            "earthscopeoceans": "*_all.txt",
            "mermaid-records": "log_gps_records.*.jsonl",
        }
        parsed_inputs = [
            (input_path, *self.parse_source(input_path, source_type))
            for input_path in sorted(input_directory.rglob(patterns[source_type]))
        ]
        if not parsed_inputs:
            raise RuntimeError(f"No matching {source_type} files under {input_directory}")

        planned_outputs: set[Path] = set()
        for _, station, _ in parsed_inputs:
            output_path = self.resolve_output_path(output_directory, station, source_tag)
            if output_path in planned_outputs:
                raise RuntimeError(f"Multiple inputs would write {output_path}")
            planned_outputs.add(output_path)

        outputs: list[Path] = []
        for input_path, station, records in parsed_inputs:
            output_path = self.resolve_output_path(output_directory, station, source_tag)
            selected = self.select_recent_unique(records)
            self.write_records_to_kml(selected, station, output_path, source_type, str(input_path))
            print(f"Station code: {station}\nInput GPS records: {len(records)}\nWritten placemarks: {len(selected)}\nOutput: {output_path}")
            outputs.append(output_path)
        return outputs


def add_parsers(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    file_parser = subparsers.add_parser("winnow_gps_file", help="Winnow one GPS file and write import-ready KML.", description="Winnow one local GPS source to recent unique points.")
    configure_parser(file_parser, input_kind="file")
    file_parser.set_defaults(handler=run_file)
    directory_parser = subparsers.add_parser("winnow_gps_dir", help="Recursively winnow GPS files into a flat KML directory.", description="Recursively winnow one local GPS source family into a flat output directory.")
    configure_parser(directory_parser, input_kind="directory")
    directory_parser.set_defaults(handler=run_directory)


def configure_parser(parser: argparse.ArgumentParser, input_kind: str) -> None:
    sources = parser.add_mutually_exclusive_group(required=True)
    metavar = "FILE" if input_kind == "file" else "DIR"
    location = "file" if input_kind == "file" else "directory"
    sources.add_argument("--kml", type=Path, metavar=metavar, help=f"automaid {location}")
    sources.add_argument("--txt", type=Path, metavar=metavar, help=f"EarthScopeOceans.org SOM {location}")
    sources.add_argument("--jsonl", type=Path, metavar=metavar, help=f"mermaid-records GPS JSONL {location}")
    parser.add_argument("-o", "--output", type=Path, help="Output file or directory (default: $MERMAID/marinetraffic)")
    parser.add_argument("--limit", type=int, default=50, help="Number of most recent points to keep")


def selected_source(args: argparse.Namespace) -> tuple[Path, str, str]:
    for input_path, source_type, source_tag in (
        (args.kml, "automaid", "kml"),
        (args.txt, "earthscopeoceans", "txt"),
        (args.jsonl, "mermaid-records", "jsonl"),
    ):
        if input_path is not None:
            return input_path, source_type, source_tag
    raise RuntimeError("No input source selected")


def run_file(args: argparse.Namespace) -> None:
    winnower = GPSKMLWinnower(limit=args.limit)
    output_path = args.output or winnower.default_output_directory()
    input_path, source_type, source_tag = selected_source(args)
    winnower.process_file(input_path, output_path, source_type, source_tag)


def run_directory(args: argparse.Namespace) -> None:
    winnower = GPSKMLWinnower(limit=args.limit)
    output_path = args.output or winnower.default_output_directory()
    if output_path.suffix.lower() == ".kml":
        raise SystemExit("winnow_gps_dir requires -o to be a directory, not a .kml file.")
    input_path, source_type, source_tag = selected_source(args)
    outputs = winnower.process_directory(input_path, output_path, source_type, source_tag)
    print(f"Processed {len(outputs)} files.")


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="mermaid-marinetraffic")
    subparsers = parser.add_subparsers(dest="command", required=True)
    add_parsers(subparsers)
    args = parser.parse_args(argv)
    args.handler(args)


if __name__ == "__main__":
    main()
