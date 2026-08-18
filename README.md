# mermaid-marinetraffic

`mermaid-marinetraffic` prepares recent MERMAID GPS histories for MarineTraffic Custom Area imports. The `winnow_gps` command removes adjacent duplicate fixes, retains the most recent points, and writes import-ready KML.

The command accepts one explicit local GPS source per run and writes a common
KML representation for MarineTraffic import.

## Installation

From a checkout of this repository:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

If a suitable virtual environment is already active, install directly with:

```bash
python -m pip install -e .
```

The installed interface is `mermaid-marinetraffic <command> [options]`.

```bash
mermaid-marinetraffic --help
mermaid-marinetraffic --version
mermaid-marinetraffic winnow_gps --help

# Equivalent module interface
python -m mermaid_marinetraffic --help
```

## Winnow GPS histories

`mermaid-marinetraffic winnow_gps` requires exactly one of three mutually
exclusive local input options:

- `--kml FILE`: an `automaid` KML such as `$MERMAID/processed_everyone/452.020-P-21/position.kml`.
- `--txt FILE`: an EarthScopeOceans.org SOM text file such as `$MERMAID/esoloc/P0021_all.txt`.
- `--jsonl FILE`: a `mermaid-records` GPS-family JSONL file such as `$MERMAID/records/452.020-P-21/log_gps_records.452.020-P-21.jsonl`.

```bash
# automaid KML
mermaid-marinetraffic winnow_gps --kml "$MERMAID/processed_everyone/452.020-P-21/position.kml"

# EarthScopeOceans.org SOM text
mermaid-marinetraffic winnow_gps --txt "$MERMAID/esoloc/P0021_all.txt"

# mermaid-records JSONL
mermaid-marinetraffic winnow_gps --jsonl "$MERMAID/records/452.020-P-21/log_gps_records.452.020-P-21.jsonl"
```

For `--kml`, only placemarks in `<Folder id="GPS points">` are processed. For
`--jsonl`, only records with `gps_record_kind == "fix_position"` are used;
their `record_time` and `raw_values.latitude`/`longitude` fields are read, and
N/S/E/W degrees/minutes values are converted to decimal degrees. Adjacent
records are duplicates only when both datetime and latitude/longitude match.
The command retains the most recent records after deduplication.

KML station codes are derived from document names as five characters; for
example, `452.120-R-0061` becomes `R0061` and `452.020-P-24` becomes `P0024`.
Text files use their station column. JSONL verifies that `instrument_id` and
`instrument_serial` agree, so `P0021` maps to `452.020-P-21`.

## Options and output

```text
--kml FILE         automaid position.kml file
--txt FILE         EarthScopeOceans.org SOM text file
--jsonl FILE       mermaid-records GPS JSONL file
-o, --output PATH  Output file or directory (default: $MERMAID/marinetraffic)
--limit N          Number of most recent unique points to keep (default: 50)
```

Without `-o`, the command writes to `$MERMAID/marinetraffic`, creating that directory as needed. Set `MERMAID` or provide `-o` explicitly. `-o` may be a `.kml` output filename or an output directory.

Output names identify the source:

```text
recent_gps_<STATION>_src-kml.kml
recent_gps_<STATION>_src-txt.kml
recent_gps_<STATION>_src-jsonl.kml
```

Placemark names use `STATION - DD-Mon-YYYY HH:MM`. Generated KML documents include `source_type`, `source_ref`, `generated_utc`, and `limit` in `Document/ExtendedData`; source types are `automaid`, `earthscopeoceans`, and `mermaid-records`.

Release notes are maintained in `CHANGELOG.md`.
