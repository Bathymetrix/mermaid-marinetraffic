# merinetraffic

`merinetraffic` prepares recent MERMAID GPS histories for MarineTraffic Custom Area imports. The `winnow_gps` command removes adjacent duplicate fixes, retains the most recent points, and writes import-ready KML.

The included `position.kml` is a representative local KML input.

## Installation

From a checkout of this repository:

```bash
python -m pip install -e .
```

The installed interface is `merinetraffic <command> [options]`.

```bash
merinetraffic --help
merinetraffic --version
merinetraffic winnow_gps --help
```

## Winnow GPS histories

`merinetraffic winnow_gps` supports three input modes:

- **Single local KML:** pass a KML file.
- **Local batch:** use `-p/--path` with a parent directory whose station subdirectories may contain `position.kml`.
- **Online SOM batch:** use `--som-all` to fetch matching `*_all.txt` files from the SOM index. An optional station code limits this mode to one station.

```bash
# Process one KML file
merinetraffic winnow_gps position.kml

# Process station directories beneath a parent directory
merinetraffic winnow_gps --path stations_parent

# Fetch every SOM station, or one named station
merinetraffic winnow_gps --som-all
merinetraffic winnow_gps --som-all P0041
```

For local KML inputs, only placemarks in `<Folder id="GPS points">` are processed. Adjacent records are duplicates only when both datetime and latitude/longitude match. The command retains the most recent records after deduplication.

Station codes are derived from local document names as five characters; for example, `452.120-R-0061` becomes `R0061` and `452.020-P-24` becomes `P0024`.

## Options and output

```text
input_kml          KML file for single-file mode
-p, --path PATH    Parent directory for local batch mode
-o, --output PATH  Output file or directory, depending on mode
--som-all [CODE]   Process all SOM files, optionally one station
--som-url URL      SOM index URL (default: https://geoweb.princeton.edu/people/simons/SOM/)
--limit N          Number of most recent unique points to keep (default: 50)
```

By default, single-file mode writes beside its input and local batch mode writes in each station directory. In single-file mode, `-o` may be a `.kml` output filename; in either local mode it may be an output directory. Directories are created as needed.

SOM batch mode writes to `som_last_50_kml` by default, and its `-o` value must be a directory.

Output names identify the source:

```text
recent_gps_<STATION>_src-kml.kml
recent_gps_<STATION>_src-som-all.kml
```

Placemark names use `STATION - DD-Mon-YYYY HH:MM`. Generated KML documents include `source_type`, `source_ref`, `generated_utc`, and `limit` in `Document/ExtendedData`.

Release notes are maintained in `CHANGELOG.md`.
