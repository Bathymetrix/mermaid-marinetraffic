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

`trajectory` uses the complete valid, adjacent-deduplicated GPS history unless
`--limit N` is supplied. Its KML contains exactly one chronological LineString
(oldest to newest), with no Point or Polygon geometry.

`points` retains the alternate individual-point product: one Point Placemark
per selected GPS fix, with the established station/timestamp names.

`polygon` writes exactly one Polygon: a 36-vertex geodesic pseudo-circle around
the latest valid deduplicated GPS fix. It requires `-r` / `--radius` in
kilometers and does not accept `--limit`.

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

# Polygon-only 1,000 km radius around the latest GPS fix
mermaid-marinetraffic polygon --jsonl "$MERMAID/records/452.020-P-21/log_gps_records.452.020-P-21.jsonl" -r 1000
```

All commands require exactly one input source. Prefer `--vit` when it is
available: if a float's `.cmd` file specifies `upload 0`, its VIT file is the
only location source because no GPS-bearing MER, LOG, or BIN files are
uploaded. Both `--vit` and `--eso` read local files; neither requires an
internet connection.

- `--vit PATH`: a MERMAID `<serial_id>.vit` log file.
- `--kml PATH`: automaid `position.kml`, for example
  `$MERMAID/processed_everyone/452.020-P-21/position.kml`.
- `--eso PATH`: ESO (EarthScope-Oceans) local location file, for example
  `$MERMAID/esoloc/P0021_all.txt`.
- `--jsonl PATH`: mermaid-records GPS JSONL, for example
  `$MERMAID/records/452.020-P-21/log_gps_records.452.020-P-21.jsonl`.

VIT files are float-derived operational data assembled by the float itself,
not first-class source records. This tool therefore scans them only for
GPS-like timestamp/coordinate lines and ignores all other content, including
malformed text. It does not attempt lossless VIT preservation; use
`mermaid-records` for the first-class BIN, LOG, and MER record families.

Each `PATH` can be a file or a directory. Directory inputs are recursive and
discover only `position.kml`, `*_all.txt`, `log_gps_records.*.jsonl` with
its optional `mer_environment_records.*.jsonl` companion, or `*.vit`,
respectively. Batch outputs are flat and the
command stops if two inputs would have the same destination filename.

KML input uses only `<Folder id="GPS points">`. JSONL uses
`gps_record_kind == "fix_position"` and `environment_kind == "gpsinfo"`,
validates instrument identity, and converts both supported coordinate formats
to decimal degrees. When present, the same-serial
`mer_environment_records.*.jsonl` companion is incorporated automatically.

## History selection and size limit

`--limit N` means exactly the number of most recent unique GPS fixes after
adjacent duplicate removal and chronological ordering. Without it, all
available valid fixes are used. Zero and negative values are rejected.

MarineTraffic advertises a `MAX 400KB` upload limit. This package enforces a
conservative 400,000-byte ceiling on the actual serialized KML bytes. It never
silently truncates, down-samples, or writes an oversized product. If a product
is too large, it reports the actual byte size and the exact largest
`--limit N` that fits the same rendered schema.

### MarineTraffic importer behavior (empirical observations)

MarineTraffic’s upload UI currently states that uploads are one file at a time,
at most 400 KB, with at most 50 geometries; geometry names must be at most 80
characters and coordinates must be in longitude/latitude order. These are
published upload limits, not a complete importer specification.

In testing, a valid, approximately 22 KB KML with two geometries failed to
import when its LineString began with an approximately 16,000 km jump from
`6.038133,43.108050,0` to approximately
`-149.574483,-17.566667,0`. Removing only that first coordinate allowed the
remaining 809-coordinate LineString to import successfully. Thus, large
LineString vertex counts were not the cause in this test; the importer appears
to perform additional geometry or continuity validation. Its exact rule or
threshold is unknown.

`mermaid-marinetraffic` currently does not check segment distances, detect or
reject geographic discontinuities, remove outliers, or split trajectories into
multiple LineStrings. Such validation may be considered later but is
intentionally out of scope for the current implementation.

Standalone trajectory, Point, and Polygon KML products have imported
successfully in testing, while KML files combining otherwise known-good
geometry types have behaved inconsistently or failed. Therefore this package
intentionally writes separate product files containing a single geometry type:
trajectory is LineString-only, points is Point-only, and polygon is
Polygon-only. This is an empirical importer behavior, not a documented
MarineTraffic specification.

## Output

Without `-o`, outputs go to `$MERMAID/marinetraffic`. For a single input,
`-o` may be a KML filename or directory; directory input requires an output
directory.

```text
gps_trajectory_<STATION>_src-kml.kml
gps_trajectory_<STATION>_src-eso.kml
gps_trajectory_<STATION>_src-jsonl.kml
gps_trajectory_<STATION>_src-vit.kml
gps_points_<STATION>_src-kml.kml
gps_points_<STATION>_src-eso.kml
gps_points_<STATION>_src-jsonl.kml
gps_points_<STATION>_src-vit.kml
gps_polygon_<STATION>_src-kml.kml
gps_polygon_<STATION>_src-eso.kml
gps_polygon_<STATION>_src-jsonl.kml
gps_polygon_<STATION>_src-vit.kml
```

Generated KML includes concise provenance metadata: source type/reference,
generation time, geometry product, number of GPS fixes, and selected limit.
Polygon KML also records `radius_km`. Its spherical destination-point ring has
36 vertices at bearings 0 through 350 degrees in 10-degree steps, followed by
the first coordinate again to close the LinearRing (37 serialized coordinates).
