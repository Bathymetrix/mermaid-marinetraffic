# mermaid-marinetraffic

`mermaid-marinetraffic` prepares recent MERMAID GPS histories for MarineTraffic Custom Area imports. The `winnow_gps` command removes adjacent duplicate fixes, retains the most recent points, and writes import-ready KML.

The included `position.kml` is a representative local KML input.

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

`mermaid-marinetraffic winnow_gps` supports three input modes:

- **Single local KML:** pass a KML file.
- **Local batch:** use `-p/--path` with a parent directory whose station subdirectories may contain `position.kml`.
- **Online SOM batch:** use `--som-all` to fetch matching `*_all.txt` files from the SOM index. An optional station code limits this mode to one station.

```bash
# Process one KML file
mermaid-marinetraffic winnow_gps position.kml

# Process station directories beneath a parent directory
mermaid-marinetraffic winnow_gps --path stations_parent

# Fetch every SOM station, or one named station
mermaid-marinetraffic winnow_gps --som-all
mermaid-marinetraffic winnow_gps --som-all P0041
```

For local KML inputs, only placemarks in `<Folder id="GPS points">` are processed. Adjacent records are duplicates only when both datetime and latitude/longitude match. The command retains the most recent records after deduplication.

Station codes are derived from local document names as five characters; for example, `452.120-R-0061` becomes `R0061` and `452.020-P-24` becomes `P0024`.

## Options and output

```text
input_kml          KML file for single-file mode
-p, --path PATH    Parent directory for local batch mode
-o, --output PATH  Output file or directory (default: $MERMAID/marinetraffic)
--som-all [CODE]   Process all SOM files, optionally one station
--som-url URL      SOM index URL (default: https://geoweb.princeton.edu/people/simons/SOM/)
--limit N          Number of most recent unique points to keep (default: 50)
```

Without `-o`, all modes write to `$MERMAID/marinetraffic`, creating that directory as needed. Set `MERMAID` or provide `-o` explicitly. In single-file mode, `-o` may be a `.kml` output filename; in either local mode it may be an output directory.

SOM batch mode requires `-o` to be a directory when it is supplied.

Output names identify the source:

```text
recent_gps_<STATION>_src-kml.kml
recent_gps_<STATION>_src-som-all.kml
```

Placemark names use `STATION - DD-Mon-YYYY HH:MM`. Generated KML documents include `source_type`, `source_ref`, `generated_utc`, and `limit` in `Document/ExtendedData`.

Release notes are maintained in `CHANGELOG.md`.
