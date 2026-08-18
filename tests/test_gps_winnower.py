"""Focused tests for deterministic GPS KML winnowing behavior."""

from datetime import datetime
from pathlib import Path
import xml.etree.ElementTree as ET

from gps_winnower import GPSKMLWinnower, KML_NS


def test_station_code_and_default_filename() -> None:
    assert GPSKMLWinnower.extract_station_code("452.120-R-0061") == "R0061"
    assert GPSKMLWinnower.extract_station_code("452.020-P-24") == "P0024"
    assert (
        GPSKMLWinnower.build_default_output_filename("R0061", "kml")
        == "recent_gps_R0061_src-kml.kml"
    )


def test_datetime_parsing_and_formatting() -> None:
    winnower = GPSKMLWinnower()
    parsed = winnower.parse_point_datetime("06/03/24 13:45")
    assert parsed == datetime(2024, 3, 6, 13, 45)
    assert winnower.format_output_datetime(parsed) == "06-Mar-2024 13:45"


def test_select_recent_unique_removes_adjacent_duplicates() -> None:
    winnower = GPSKMLWinnower(limit=2)
    records = [
        (datetime(2024, 1, 1, 12), ("1", "2"), "first"),
        (datetime(2024, 1, 1, 12), ("1", "2"), "duplicate"),
        (datetime(2024, 1, 2, 12), ("3", "4"), "second"),
        (datetime(2024, 1, 3, 12), ("1", "2"), "third"),
    ]

    selected = winnower.select_recent_unique(records)

    assert [record[2] for record in selected] == ["third", "second"]


def test_process_kml_file_writes_expected_records_and_metadata(tmp_path: Path) -> None:
    input_path = tmp_path / "position.kml"
    output_path = tmp_path / "output.kml"
    input_path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document>
  <name>452.020-P-24</name>
  <Folder id="GPS points">
    <Placemark><name>01/01/24 10:00</name><Point><coordinates>2,1,0</coordinates></Point></Placemark>
    <Placemark><name>01/01/24 10:00</name><Point><coordinates>2,1,0</coordinates></Point></Placemark>
    <Placemark><name>02/01/24 10:00</name><Point><coordinates>4,3,0</coordinates></Point></Placemark>
  </Folder>
</Document></kml>""",
        encoding="utf-8",
    )

    result = GPSKMLWinnower(limit=1).process_kml_file(input_path, output_path)
    root = ET.parse(result).getroot()
    namespace = {"k": KML_NS}

    placemarks = root.findall(".//k:Folder/k:Placemark", namespace)
    assert result == output_path
    assert [item.findtext("k:name", namespaces=namespace) for item in placemarks] == [
        "P0024 - 02-Jan-2024 10:00"
    ]
    metadata = {
        item.get("name"): item.findtext("k:value", namespaces=namespace)
        for item in root.findall(".//k:ExtendedData/k:Data", namespace)
    }
    assert metadata["source_type"] == "kml"
    assert metadata["source_ref"] == str(input_path)
    assert metadata["limit"] == "1"
