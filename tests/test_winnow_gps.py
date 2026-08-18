"""Focused tests for the winnow_gps command and local source parsers."""

from datetime import datetime
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from mermaid_marinetraffic import __version__, cli, winnow_gps

FIXTURES = Path(__file__).parent / "fixtures"


def test_top_level_help_and_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit, match="0"):
        cli.main(["--help"])
    assert "winnow_gps" in capsys.readouterr().out
    with pytest.raises(SystemExit, match="0"):
        cli.main(["--version"])
    assert capsys.readouterr().out.strip() == __version__


def test_winnow_gps_requires_exactly_one_local_source(capsys: pytest.CaptureFixture[str]) -> None:
    parser = cli.build_parser()
    with pytest.raises(SystemExit, match="2"):
        parser.parse_args(["winnow_gps"])
    with pytest.raises(SystemExit, match="2"):
        parser.parse_args(["winnow_gps", "--kml", "a.kml", "--txt", "a.txt"])
    with pytest.raises(SystemExit, match="0"):
        cli.main(["winnow_gps", "--help"])
    output = capsys.readouterr().out
    assert all(option in output for option in ("--kml FILE", "--txt FILE", "--jsonl FILE"))
    assert "--som-all" not in output and "--path" not in output


def test_default_output_directory_uses_mermaid_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MERMAID", str(tmp_path))
    assert winnow_gps.GPSKMLWinnower.default_output_directory() == tmp_path / "marinetraffic"


def test_station_code_datetime_and_json_coordinate_parsing() -> None:
    winnower = winnow_gps.GPSKMLWinnower()
    assert winnower.extract_station_code("452.020-P-21") == "P0021"
    assert winnower.parse_point_datetime("06/03/24 13:45") == datetime(2024, 3, 6, 13, 45)
    assert winnower.parse_degrees_minutes("S23deg38.830mn") == "-23.647167"
    assert winnower.parse_degrees_minutes("E007deg19.164mn") == "7.319400"


def test_default_filenames_keep_source_option_tags() -> None:
    assert winnow_gps.GPSKMLWinnower.build_default_output_filename("P0021", "kml") == "recent_gps_P0021_src-kml.kml"
    assert winnow_gps.GPSKMLWinnower.build_default_output_filename("P0021", "txt") == "recent_gps_P0021_src-txt.kml"
    assert winnow_gps.GPSKMLWinnower.build_default_output_filename("P0021", "jsonl") == "recent_gps_P0021_src-jsonl.kml"


@pytest.mark.parametrize(
    ("option", "fixture_name", "source_type"),
    [
        ("--kml", "P0021_position.kml", "automaid"),
        ("--txt", "P0021_all.txt", "earthscopeoceans"),
        ("--jsonl", "log_gps_records.452.020-P-21.jsonl", "mermaid-records"),
    ],
)
def test_each_local_source_writes_uniform_kml(tmp_path: Path, option: str, fixture_name: str, source_type: str) -> None:
    output = tmp_path / "output.kml"
    cli.main(["winnow_gps", option, str(FIXTURES / fixture_name), "-o", str(output), "--limit", "3"])
    root = ET.parse(output).getroot()
    namespace = {"k": winnow_gps.KML_NS}
    placemarks = root.findall(".//k:Folder/k:Placemark", namespace)
    metadata = {item.get("name"): item.findtext("k:value", namespaces=namespace) for item in root.findall(".//k:ExtendedData/k:Data", namespace)}
    assert len(placemarks) == 3
    assert all(item.findtext("k:name", namespaces=namespace).startswith("P0021 - ") for item in placemarks)
    assert metadata["source_type"] == source_type
    assert metadata["source_ref"] == str(FIXTURES / fixture_name)


def test_jsonl_parser_accepts_only_fix_position_records() -> None:
    station, records = winnow_gps.GPSKMLWinnower().parse_jsonl(FIXTURES / "log_gps_records.452.020-P-21.jsonl")
    assert station == "P0021"
    assert records[0].timestamp == datetime(2018, 6, 13, 9, 49, 48)
    assert records[0].latitude == "43.682650"
    assert records[0].longitude == "7.319400"
