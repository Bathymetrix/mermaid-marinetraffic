# merinetraffic

`merinetraffic` prepares recent MERMAID position histories for MarineTraffic Custom Area imports. Its single script, `gps_winnower.py`, reads position data, removes adjacent duplicate fixes, keeps the most recent points, and writes a KML file for import.

The included `position.kml` is a representative local KML input.

## Input modes

`gps_winnower.py` supports three mutually exclusive modes:

- **Single local KML:** pass a KML file as `input_kml`.
- **Local batch:** pass a parent directory with `-p/--path`; each station subdirectory may contain `position.kml`.
- **Online SOM batch:** pass `--som-all` to fetch matching `*_all.txt` files from the SOM index.

For local KML inputs, only placemarks in `<Folder id="GPS points">` are processed. Adjacent records are considered duplicates only when both their datetime and latitude/longitude match. After deduplication, the most recent records are retained.

Station codes are derived from the source document name as five characters. For example, `452.120-R-0061` becomes `R0061`, and `452.020-P-24` becomes `P0024`.

## Usage

```bash
# Process one KML file
python3 gps_winnower.py position.kml

# Process station directories beneath a parent directory
python3 gps_winnower.py -p stations_parent

# Fetch and process SOM *_all.txt files
python3 gps_winnower.py --som-all
```

## Options

```text
input_kml          KML file for single-file mode
-p, --path PATH    Parent directory for local batch mode
-o, --output PATH  Output file or directory, depending on mode
--som-all          Process all matching SOM *_all.txt files
--som-url URL      SOM index URL (default: https://geoweb.princeton.edu/people/simons/SOM/)
--limit N          Number of most recent unique points to keep (default: 50)
--version          Print the version from VERSION
```

## Output

By default, single-file mode writes beside its input and local batch mode writes in each station directory. In either local mode, `-o` may be a `.kml` filename for single-file mode or a directory for either mode; directories are created as needed.

SOM batch mode writes to `som_last_50_kml` by default. Its `-o` value must be a directory.

Default output names identify the source:

```text
recent_gps_<STATION>_src-kml.kml
recent_gps_<STATION>_src-som-all.kml
```

Placemark names use `STATION - DD-Mon-YYYY HH:MM`. Generated KML documents include `source_type`, `source_ref`, `generated_utc`, and `limit` in `Document/ExtendedData`.

## Version

```bash
python3 gps_winnower.py --version
```

Release notes are maintained in `CHANGELOG.md`.
