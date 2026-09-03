"""Focused tests for trajectory and individual-point KML products."""

from datetime import datetime
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from mermaid_marinetraffic import __version__, cli, winnow_gps

FIXTURES = Path(__file__).parent / "fixtures"
NS = {"k": winnow_gps.KML_NS}
GENERATED_UTC = "2026-08-18T12:00:00Z"


def records() -> list[winnow_gps.PositionRecord]:
    return [
        winnow_gps.PositionRecord(datetime(2024, 1, 3), "3", "30"),
        winnow_gps.PositionRecord(datetime(2024, 1, 1), "1", "10"),
        winnow_gps.PositionRecord(datetime(2024, 1, 1), "1", "10"),
        winnow_gps.PositionRecord(datetime(2024, 1, 2), "2", "20"),
    ]


def parse(data: bytes) -> ET.Element:
    return ET.fromstring(data)


def test_top_level_help_version_and_product_commands(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit, match="0"):
        cli.main(["--help"])
    help_text = capsys.readouterr().out
    assert "trajectory" in help_text and "points" in help_text
    assert "winnow_gps" not in help_text
    for command in ("trajectory", "points"):
        with pytest.raises(SystemExit, match="0"):
            cli.main([command, "--help"])
        assert "--limit N" in capsys.readouterr().out
    with pytest.raises(SystemExit, match="0"):
        cli.main(["--version"])
    assert capsys.readouterr().out.strip() == __version__


def test_selection_defaults_to_complete_ordered_history_and_limit_is_recent() -> None:
    assert [record.latitude for record in winnow_gps.GPSKMLWinnower().select_records(records())] == ["1", "2", "3"]
    assert [record.latitude for record in winnow_gps.GPSKMLWinnower(limit=2).select_records(records())] == ["2", "3"]


def test_trajectory_has_ordered_linestring_latest_point_styles_and_provenance() -> None:
    winnower = winnow_gps.GPSKMLWinnower(limit=2)
    data = winnower.render_kml_bytes(
        winnower.select_records(records()), "P0021", "automaid", "/input/position.kml",
        "trajectory", GENERATED_UTC,
    )
    root = parse(data)
    line_coordinates = root.findtext(".//k:LineString/k:coordinates", namespaces=NS)
    assert line_coordinates.splitlines() == ["20,2,0", "30,3,0"]
    latest_coordinates = root.findtext(".//k:Placemark[k:name='P0021 - latest - 03-Jan-2024 00:00']/k:Point/k:coordinates", namespaces=NS)
    assert latest_coordinates == "30,3,0"
    assert root.findtext(".//k:Placemark[k:name='P0021 trajectory']/k:styleUrl", namespaces=NS) == "#trajectory"
    assert root.findtext(".//k:Placemark[k:Point]/k:styleUrl", namespaces=NS) == "#latest-position"
    assert root.findtext(".//k:Style[@id='trajectory']/k:LineStyle/k:width", namespaces=NS) == "3"
    assert root.findtext(".//k:Style[@id='latest-position']/k:IconStyle/k:scale", namespaces=NS) == "1.8"
    metadata = {item.get("name"): item.findtext("k:value", namespaces=NS) for item in root.findall(".//k:Data", NS)}
    assert metadata == {
        "source_type": "automaid", "source_ref": "/input/position.kml",
        "generated_utc": GENERATED_UTC, "geometry_type": "trajectory",
        "gps_points": "2", "limit": "2",
    }


def test_single_fix_trajectory_preserves_latest_position_without_degenerate_line() -> None:
    data = winnow_gps.GPSKMLWinnower().render_kml_bytes(
        records()[:1], "P0021", "automaid", "/input", "trajectory", GENERATED_UTC
    )
    root = parse(data)
    assert root.find(".//k:LineString", NS) is None
    assert root.findtext(".//k:Point/k:coordinates", namespaces=NS) == "30,3,0"


def test_points_renderer_emits_one_point_per_selected_fix() -> None:
    selected = winnow_gps.GPSKMLWinnower(limit=2).select_records(records())
    root = parse(winnow_gps.GPSKMLWinnower(limit=2).render_kml_bytes(
        selected, "P0021", "automaid", "/input", "points", GENERATED_UTC
    ))
    placemarks = root.findall(".//k:Placemark", NS)
    assert len(placemarks) == 2
    assert [item.findtext("k:name", namespaces=NS) for item in placemarks] == [
        "P0021 - 02-Jan-2024 00:00", "P0021 - 03-Jan-2024 00:00"
    ]
    assert all(item.findtext("k:styleUrl", namespaces=NS) == "#gps-point" for item in placemarks)


def test_json_coordinate_and_identity_parsing() -> None:
    station, parsed = winnow_gps.GPSKMLWinnower().parse_jsonl(FIXTURES / "log_gps_records.452.020-P-21.jsonl")
    assert station == "P0021"
    assert parsed[0].timestamp == datetime(2018, 6, 13, 9, 49, 48)
    assert parsed[0].latitude == "43.682650"
    assert parsed[0].longitude == "7.319400"


def test_jsonl_incorporates_mer_environment_gpsinfo(tmp_path: Path) -> None:
    identity = {"instrument_id": "P0021", "instrument_serial": "452.020-P-21"}
    log_path = tmp_path / "log_gps_records.452.020-P-21.jsonl"
    environment_path = tmp_path / "mer_environment_records.452.020-P-21.jsonl"
    log_path.write_text(json.dumps({
        **identity, "gps_record_kind": "fix_position",
        "record_time": "2024-02-07T22:47:20.000000Z",
        "raw_values": {"latitude": "N28deg45.600mn", "longitude": "E138deg48.000mn"},
    }) + "\n", encoding="utf-8")
    environment_path.write_text(json.dumps({
        **identity, "environment_kind": "gpsinfo",
        "gpsinfo_date": "2024-02-07T22:47:22.000000Z",
        "raw_values": {"date": "2024-02-07T22:47:22", "lat": "+2845.7300", "lon": "+13848.3010"},
    }) + "\n", encoding="utf-8")

    station, parsed = winnow_gps.GPSKMLWinnower().parse_jsonl(log_path)

    assert station == "P0021"
    assert [(record.timestamp, record.latitude, record.longitude) for record in parsed] == [
        (datetime(2024, 2, 7, 22, 47, 20), "28.760000", "138.800000"),
        (datetime(2024, 2, 7, 22, 47, 22), "28.762167", "138.805017"),
    ]


def test_vit_timestamp_coordinate_and_filename_station_parsing() -> None:
    station, parsed = winnow_gps.GPSKMLWinnower().parse_vit(
        FIXTURES / "452.020-P-21.vit"
    )
    assert station == "P0021"
    assert parsed == [
        winnow_gps.PositionRecord(
            datetime(2018, 6, 28, 7, 22, 36), "43.108067", "6.038067"
        ),
        winnow_gps.PositionRecord(
            datetime(2018, 8, 17, 0, 30, 6), "-17.566667", "-149.574500"
        ),
    ]


def test_vit_ignores_invalid_utf8_outside_gps_lines(tmp_path: Path) -> None:
    input_path = tmp_path / "452.020-P-21.vit"
    input_path.write_bytes(
        b"20260818-07h13mn31: S23deg22.941mn, W140deg02.888mn\n"
        b"status: bad\xd0\xdf\xff text\n",
    )

    station, parsed = winnow_gps.GPSKMLWinnower().parse_vit(input_path)

    assert station == "P0021"
    assert parsed == [
        winnow_gps.PositionRecord(
            datetime(2026, 8, 18, 7, 13, 31), "-23.382350", "-140.048133"
        )
    ]


@pytest.mark.parametrize(
    ("option", "fixture_name", "source_type"),
    [
        ("--kml", "P0021_position.kml", "automaid"),
        ("--eso", "P0021_all.txt", "earthscopeoceans"),
        ("--jsonl", "log_gps_records.452.020-P-21.jsonl", "mermaid-records"),
        ("--vit", "452.020-P-21.vit", "vit"),
    ],
)
def test_trajectory_accepts_each_file_source(tmp_path: Path, option: str, fixture_name: str, source_type: str) -> None:
    output = tmp_path / "trajectory.kml"
    cli.main(["trajectory", option, str(FIXTURES / fixture_name), "-o", str(output), "--limit", "3"])
    root = ET.parse(output).getroot()
    assert root.find(".//k:LineString", NS) is not None
    assert root.find(".//k:Point", NS) is not None
    metadata = {item.get("name"): item.findtext("k:value", namespaces=NS) for item in root.findall(".//k:Data", NS)}
    assert metadata["source_type"] == source_type


def test_directory_source_writes_flat_trajectory_output(tmp_path: Path) -> None:
    input_file = tmp_path / "processed" / "452.020-P-21" / "position.kml"
    input_file.parent.mkdir(parents=True)
    input_file.write_bytes((FIXTURES / "P0021_position.kml").read_bytes())
    output_directory = tmp_path / "output"
    cli.main(["trajectory", "--kml", str(tmp_path / "processed"), "-o", str(output_directory), "--limit", "2"])
    assert list(output_directory.iterdir()) == [output_directory / "gps_trajectory_P0021_src-kml.kml"]


def test_points_command_writes_points_product(tmp_path: Path) -> None:
    output = tmp_path / "points.kml"
    cli.main(["points", "--eso", str(FIXTURES / "P0021_all.txt"), "-o", str(output), "--limit", "2"])
    assert len(ET.parse(output).getroot().findall(".//k:Point", NS)) == 2


def test_size_limit_reports_exact_largest_fitting_limit() -> None:
    all_records = winnow_gps.GPSKMLWinnower().ordered_unique_records(records())
    baseline = winnow_gps.GPSKMLWinnower()
    size_for_two = len(baseline.render_kml_bytes(all_records[-2:], "P0021", "automaid", "/input", "trajectory", GENERATED_UTC))
    winnower = winnow_gps.GPSKMLWinnower(max_kml_bytes=size_for_two)
    fitting = winnower.render_kml_bytes(all_records[-2:], "P0021", "automaid", "/input", "trajectory", GENERATED_UTC)
    oversized = winnower.render_kml_bytes(all_records, "P0021", "automaid", "/input", "trajectory", GENERATED_UTC)
    winnower.enforce_size(fitting, all_records, "P0021", "automaid", "/input", "trajectory", GENERATED_UTC)
    with pytest.raises(winnow_gps.KMLSizeError) as error:
        winnower.enforce_size(oversized, all_records, "P0021", "automaid", "/input", "trajectory", GENERATED_UTC)
    assert f"KML size:           {len(oversized)} bytes" in str(error.value)
    assert "Maximum GPS points: 2" in str(error.value)
    assert "Rerun with --limit 2 or smaller." in str(error.value)


def test_oversize_prevents_output_and_invalid_limit_is_rejected(tmp_path: Path) -> None:
    output = tmp_path / "too-large.kml"
    winnower = winnow_gps.GPSKMLWinnower(max_kml_bytes=1)
    with pytest.raises(winnow_gps.KMLSizeError):
        winnower.prepare_product(FIXTURES / "P0021_position.kml", "automaid", "kml", "trajectory", output, GENERATED_UTC)
    assert not output.exists()
    with pytest.raises(SystemExit, match="2"):
        cli.main(["trajectory", "--kml", "input.kml", "--limit", "0"])
