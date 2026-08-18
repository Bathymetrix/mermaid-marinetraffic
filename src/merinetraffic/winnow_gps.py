#!/usr/bin/env python3
"""Core winnower logic for MERMAID KML positional metadata."""

from __future__ import annotations

import argparse
import heapq
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from copy import deepcopy
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

KML_NS = "http://www.opengis.net/kml/2.2"
GX_NS = "http://www.google.com/kml/ext/2.2"
NS = {"k": KML_NS}
SOM_DEFAULT_URL = "https://geoweb.princeton.edu/people/simons/SOM/"


class LinkExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        for key, value in attrs:
            if key == "href" and value:
                self.links.append(value)


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

        after_first_dash = document_name.split("-", 1)[1]
        alnum = "".join(ch for ch in after_first_dash if ch.isalnum())
        if len(alnum) < 2:
            raise ValueError(f"Cannot derive station code from: {document_name!r}")

        first = alnum[0]
        last = alnum[-1]
        middle = alnum[1:-1]
        zeros_needed = 5 - (1 + len(middle) + 1)
        if zeros_needed < 0:
            middle = middle[-3:]
            zeros_needed = 0
        return f"{first}{'0' * zeros_needed}{middle}{last}"

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
    def parse_lat_lon(coords_text: str) -> tuple[str, str]:
        parts = [p.strip() for p in coords_text.strip().split(",")]
        if len(parts) < 2:
            raise ValueError(f"Invalid coordinates text: {coords_text!r}")
        return parts[0], parts[1]

    @staticmethod
    def get_text(el: ET.Element | None) -> str:
        return (el.text or "").strip() if el is not None and el.text is not None else ""

    @staticmethod
    def resolve_output_path(
        input_path: Path, station: str, output_path: Path | None, source_tag: str
    ) -> Path:
        default_name = GPSKMLWinnower.build_default_output_filename(station, source_tag)
        if output_path is None:
            return input_path.parent / default_name
        if output_path.exists() and output_path.is_dir():
            return output_path / default_name
        if output_path.suffix.lower() == ".kml":
            output_path.parent.mkdir(parents=True, exist_ok=True)
            return output_path
        output_path.mkdir(parents=True, exist_ok=True)
        return output_path / default_name

    def select_recent_unique(
        self, records: list[tuple[datetime, tuple[str, str], object]]
    ) -> list[tuple[datetime, tuple[str, str], object]]:
        deduped: list[tuple[datetime, tuple[str, str], object]] = []
        prev_key: tuple[datetime, tuple[str, str]] | None = None
        for dt, lat_lon, raw_item in records:
            key = (dt, lat_lon)
            if key == prev_key:
                continue
            deduped.append((dt, lat_lon, raw_item))
            prev_key = key
        return heapq.nlargest(self.limit, deduped, key=lambda x: x[0])

    def write_records_to_kml(
        self,
        records: list[tuple[datetime, tuple[str, str], object]],
        station: str,
        output_path: Path,
        document_name: str | None = None,
        source_type: str = "unknown",
        source_ref: str = "",
    ) -> None:
        out_root = ET.Element(f"{{{KML_NS}}}kml")
        out_doc = ET.SubElement(out_root, f"{{{KML_NS}}}Document")

        out_doc_name = ET.SubElement(out_doc, f"{{{KML_NS}}}name")
        out_doc_name.text = document_name or station
        out_desc = ET.SubElement(out_doc, f"{{{KML_NS}}}description")
        out_desc.text = f"Generated from {source_type} input"

        ext = ET.SubElement(out_doc, f"{{{KML_NS}}}ExtendedData")
        metadata = {
            "source_type": source_type,
            "source_ref": source_ref,
            "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "limit": str(self.limit),
        }
        for key, value in metadata.items():
            data = ET.SubElement(ext, f"{{{KML_NS}}}Data", {"name": key})
            val = ET.SubElement(data, f"{{{KML_NS}}}value")
            val.text = value

        out_folder = ET.SubElement(out_doc, f"{{{KML_NS}}}Folder", {"id": "GPS points"})
        out_folder_name = ET.SubElement(out_folder, f"{{{KML_NS}}}name")
        out_folder_name.text = "GPS points"

        for dt, lat_lon, raw_item in records:
            if isinstance(raw_item, ET.Element):
                cloned = deepcopy(raw_item)
                out_name = cloned.find("k:name", NS)
                if out_name is None:
                    out_name = ET.SubElement(cloned, f"{{{KML_NS}}}name")
                out_name.text = f"{station} - {self.format_output_datetime(dt)}"
                out_folder.append(cloned)
                continue

            placemark = ET.SubElement(out_folder, f"{{{KML_NS}}}Placemark")
            out_name = ET.SubElement(placemark, f"{{{KML_NS}}}name")
            out_name.text = f"{station} - {self.format_output_datetime(dt)}"
            visibility = ET.SubElement(placemark, f"{{{KML_NS}}}visibility")
            visibility.text = "1"
            style_url = ET.SubElement(placemark, f"{{{KML_NS}}}styleUrl")
            style_url.text = "#markerStyle2"
            point = ET.SubElement(placemark, f"{{{KML_NS}}}Point")
            coords = ET.SubElement(point, f"{{{KML_NS}}}coordinates")
            coords.text = f"{lat_lon[1]},{lat_lon[0]},0"

        ET.indent(out_root, space="    ")
        ET.ElementTree(out_root).write(output_path, encoding="UTF-8", xml_declaration=True)

    def process_kml_file(self, input_path: Path, output_path: Path | None = None) -> Path:
        tree = ET.parse(input_path)
        root = tree.getroot()

        document = root.find("k:Document", NS)
        if document is None:
            raise RuntimeError("No <Document> found")

        doc_name_el = document.find("k:name", NS)
        document_name = self.get_text(doc_name_el)
        if not document_name:
            raise RuntimeError("No document <name> found")

        station = self.extract_station_code(document_name)
        gps_folder = document.find("k:Folder[@id='GPS points']", NS)
        if gps_folder is None:
            raise RuntimeError("No <Folder id='GPS points'> found")

        placemarks = gps_folder.findall("k:Placemark", NS)
        records: list[tuple[datetime, tuple[str, str], object]] = []
        for placemark in placemarks:
            raw_name = self.get_text(placemark.find("k:name", NS))
            raw_coords = self.get_text(placemark.find(".//k:Point/k:coordinates", NS))
            if not raw_name or not raw_coords:
                continue
            dt = self.parse_point_datetime(raw_name)
            lat_lon = self.parse_lat_lon(raw_coords)
            records.append((dt, lat_lon, placemark))

        selected = self.select_recent_unique(records)
        final_output = self.resolve_output_path(input_path, station, output_path, source_tag="kml")

        self.write_records_to_kml(
            records=selected,
            station=station,
            output_path=final_output,
            document_name=document_name,
            source_type="kml",
            source_ref=str(input_path),
        )

        print(f"Station code: {station}")
        print(f"Input GPS placemarks: {len(placemarks)}")
        print(f"Written placemarks: {len(selected)}")
        print(f"Output: {final_output}")
        return final_output

    def process_kml_directory(
        self, parent_dir: Path, output_dir: Path | None = None
    ) -> tuple[int, int, list[tuple[Path, str]]]:
        if not parent_dir.is_dir():
            raise RuntimeError(f"Not a directory: {parent_dir}")

        processed = 0
        skipped = 0
        skipped_dirs: list[tuple[Path, str]] = []

        if output_dir is not None:
            output_dir.mkdir(parents=True, exist_ok=True)

        for station_dir in sorted(parent_dir.iterdir()):
            if not station_dir.is_dir() or station_dir.name.startswith("."):
                continue

            input_kml = station_dir / "position.kml"
            if not input_kml.exists():
                skipped += 1
                skipped_dirs.append((station_dir, "missing position.kml"))
                continue

            print(f"\nProcessing {input_kml}")
            try:
                self.process_kml_file(input_kml, output_path=output_dir)
                processed += 1
            except Exception as exc:  # noqa: BLE001
                skipped += 1
                skipped_dirs.append((station_dir, str(exc)))
                print(f"Skipped {input_kml}: {exc}")

        return processed, skipped, skipped_dirs

    @staticmethod
    def list_som_all_files(som_url: str, station: str | None = None) -> list[str]:
        with urllib.request.urlopen(som_url) as resp:
            html_text = resp.read().decode("utf-8", errors="replace")
        parser = LinkExtractor()
        parser.feed(html_text)
        pattern = re.compile(r"^[A-Z]\d{3,4}_all\.txt$")
        names = {href for href in parser.links if pattern.match(href)}
        if station:
            names = {name for name in names if name.startswith(f"{station}_")}
        return sorted(names)

    def process_online_som_all(
        self, som_url: str, output_dir: Path, station: str | None = None
    ) -> tuple[int, int, list[tuple[str, str]]]:
        output_dir.mkdir(parents=True, exist_ok=True)
        processed = 0
        skipped = 0
        skipped_files: list[tuple[str, str]] = []

        for name in self.list_som_all_files(som_url, station):
            file_url = urllib.parse.urljoin(som_url, name)
            print(f"\nProcessing {file_url}")
            try:
                with urllib.request.urlopen(file_url) as resp:
                    txt = resp.read().decode("utf-8", errors="replace")

                records: list[tuple[datetime, tuple[str, str], object]] = []
                station_seen: str | None = None

                for raw_line in txt.splitlines():
                    line = raw_line.strip()
                    if not line:
                        continue
                    parts = line.split()
                    if len(parts) < 5:
                        continue

                    station = parts[0]
                    dt = self.parse_som_datetime(f"{parts[1]} {parts[2]}")
                    lat_lon = (parts[3], parts[4])
                    station_seen = station_seen or station
                    records.append((dt, lat_lon, None))

                if not records:
                    raise RuntimeError("no valid rows found")
                if not station_seen:
                    raise RuntimeError("missing station field")

                selected = self.select_recent_unique(records)
                out_path = output_dir / self.build_default_output_filename(
                    station_seen, source_tag="som-all"
                )

                self.write_records_to_kml(
                    records=selected,
                    station=station_seen,
                    output_path=out_path,
                    document_name=station_seen,
                    source_type="txt",
                    source_ref=file_url,
                )

                print(f"Station code: {station_seen}")
                print(f"Input records: {len(records)}")
                print(f"Written placemarks: {len(selected)}")
                print(f"Output: {out_path}")
                processed += 1
            except Exception as exc:  # noqa: BLE001
                skipped += 1
                skipped_files.append((name, str(exc)))
                print(f"Skipped {file_url}: {exc}")

        return processed, skipped, skipped_files



def add_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Add the ``winnow_gps`` command to a top-level parser."""
    parser = subparsers.add_parser(
        "winnow_gps",
        help="Winnow recent GPS points and write import-ready KML.",
        description="Winnow KML to the most recent unique GPS points.",
    )
    configure_parser(parser)
    parser.set_defaults(handler=run)


def configure_parser(parser: argparse.ArgumentParser) -> None:
    """Add GPS-winnowing options to *parser*."""
    parser.add_argument(
        "input_kml",
        type=Path,
        nargs="?",
        help="Path to input .kml (single-file mode)",
    )
    parser.add_argument(
        "-p",
        "--path",
        type=Path,
        help="Parent directory containing station subdirectories with position.kml",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output path: file or directory (directory is auto-created)",
    )
    parser.add_argument(
        "--som-all",
        nargs="?",
        const="",
        metavar="STATION",
        help="Fetch all SOM *_all.txt files, optionally for one station",
    )
    parser.add_argument(
        "--som-url",
        default=SOM_DEFAULT_URL,
        help=f"SOM index URL (default: {SOM_DEFAULT_URL})",
    )
    parser.add_argument(
        "--limit", type=int, default=50, help="Number of most recent points to keep"
    )
def run(args: argparse.Namespace) -> None:
    """Run GPS winnowing from parsed command arguments."""
    winnower = GPSKMLWinnower(limit=args.limit)

    if args.som_all is not None:
        if args.input_kml or args.path:
            raise SystemExit("Use --som-all by itself (no input_kml or -p).")
        if args.output is None:
            output_dir = Path("som_last_50_kml")
        elif args.output.suffix.lower() == ".kml":
            raise SystemExit("--som-all requires -o as a directory, not a .kml file.")
        else:
            output_dir = args.output

        processed, skipped, skipped_files = winnower.process_online_som_all(
            som_url=args.som_url, output_dir=output_dir, station=args.som_all or None
        )
        print(f"\nDone. Processed: {processed}, Skipped: {skipped}")
        if skipped_files:
            print("Skipped files:")
            for name, reason in skipped_files:
                print(f"- {name} ({reason})")
        return

    if args.path:
        if args.input_kml:
            raise SystemExit("Do not pass positional input_kml when using -p.")
        processed, skipped, skipped_dirs = winnower.process_kml_directory(
            args.path, output_dir=args.output
        )
        print(f"\nDone. Processed: {processed}, Skipped: {skipped}")
        if skipped_dirs:
            print("Skipped directories:")
            for skipped_dir, reason in skipped_dirs:
                print(f"- {skipped_dir} ({reason})")
        return

    if not args.input_kml:
        raise SystemExit("Provide input_kml, or use -p, or use --som-all.")

    winnower.process_kml_file(args.input_kml, args.output)


def main(argv: Sequence[str] | None = None) -> None:
    """Run ``winnow_gps`` directly as a module-level command."""
    parser = argparse.ArgumentParser(
        prog="merinetraffic winnow_gps",
        description="Winnow KML to the most recent unique GPS points.",
    )
    configure_parser(parser)
    run(parser.parse_args(argv))


if __name__ == "__main__":
    main()
