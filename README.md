# mermaid-marinetraffic

`mermaid-marinetraffic` prepares MERMAID GPS trajectories for MarineTraffic
Custom Area KML imports. It reads validated local position histories and writes
one KML product per float.

## Installation

From a checkout:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

The installed interface is `mermaid-marinetraffic <command> [options]`.

## Products

`trajectory` is the default product model. It uses the complete valid,
adjacent-deduplicated GPS history unless `--limit N` is supplied. A trajectory
KML contains one chronological LineString (oldest to newest) and a separate
Point marking the latest fix. A one-fix history contains the useful latest
Point without a degenerate LineString.

`points` retains the alternate individual-point product: one Point Placemark
per selected GPS fix, with the established station/timestamp names.

```bash
# Complete trajectory from a single mermaid-records file
mermaid-marinetraffic trajectory \
  --jsonl "$MERMAID/records/452.020-P-21/log_gps_records.452.020-P-21.jsonl"

# Complete trajectory for every established JSONL input under records
mermaid-marinetraffic trajectory --jsonl "$MERMAID/records" \
  -o "$MERMAID/marinetraffic"

# Keep only the 50 most recent unique GPS fixes
mermaid-marinetraffic trajectory --jsonl "$MERMAID/records/452.020-P-21/log_gps_records.452.020-P-21.jsonl" --limit 50

# Alternate Point-only KML
mermaid-marinetraffic points --jsonl "$MERMAID/records/452.020-P-21/log_gps_records.452.020-P-21.jsonl"
```

All commands require exactly one input source. Prefer `--vit` when it is
available: if a float's `.cmd` file specifies `upload 0`, its VIT file is the
only location source because no GPS-bearing MER, LOG, or BIN files are
uploaded. Unlike `--txt`, which obtains comparable date and location data from
the SOM service, `--vit` reads a local file and does not require an internet
connection.

- `--vit PATH`: a MERMAID `<serial_id>.vit` log file.
- `--kml PATH`: automaid `position.kml`, for example
  `$MERMAID/processed_everyone/452.020-P-21/position.kml`.
- `--txt PATH`: EarthScopeOceans.org SOM text, for example
  `$MERMAID/esoloc/P0021_all.txt`.
- `--jsonl PATH`: mermaid-records GPS JSONL, for example
  `$MERMAID/records/452.020-P-21/log_gps_records.452.020-P-21.jsonl`.

Each `PATH` can be a file or a directory. Directory inputs are recursive and
discover only `position.kml`, `*_all.txt`, `log_gps_records.*.jsonl`, or
`*.vit`, respectively. Batch outputs are flat and the
command stops if two inputs would have the same destination filename.

KML input uses only `<Folder id="GPS points">`. JSONL uses only
`gps_record_kind == "fix_position"`, validates instrument identity, and
converts N/S/E/W degree/minute coordinates to decimal degrees.

## History selection and size limit

`--limit N` means exactly the number of most recent unique GPS fixes after
adjacent duplicate removal and chronological ordering. Without it, all
available valid fixes are used. Zero and negative values are rejected.

MarineTraffic advertises a `MAX 400KB` upload limit. This package enforces a
conservative 400,000-byte ceiling on the actual serialized KML bytes. It never
silently truncates, down-samples, or writes an oversized product. If a product
is too large, it reports the actual byte size and the exact largest
`--limit N` that fits the same rendered schema.

## Output

Without `-o`, outputs go to `$MERMAID/marinetraffic`. For a single input,
`-o` may be a KML filename or directory; directory input requires an output
directory.

```text
gps_trajectory_<STATION>_src-kml.kml
gps_trajectory_<STATION>_src-txt.kml
gps_trajectory_<STATION>_src-jsonl.kml
gps_trajectory_<STATION>_src-vit.kml
gps_points_<STATION>_src-kml.kml
gps_points_<STATION>_src-txt.kml
gps_points_<STATION>_src-jsonl.kml
gps_points_<STATION>_src-vit.kml
```

Generated KML includes concise provenance metadata: source type/reference,
generation time, geometry product, number of GPS fixes, and selected limit.
Trajectory KML uses distinct document-level styles for its historical line and
emphasized latest position.
