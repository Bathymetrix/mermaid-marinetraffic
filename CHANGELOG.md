# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project follows Semantic Versioning.

## Unreleased

### Changed
- Replaced positional, batch, and online GPS inputs with required local `--kml`, `--txt`, and `--jsonl` sources.
- Unified all source parsers into shared deduplication, recent-N selection, and KML writing; KML provenance now identifies `automaid`, EarthScopeOceans.org, or `mermaid-records`.
- Simplified repository instructions, documentation, and local-file ignore rules.
- Added focused tests for deterministic KML winnowing behavior.
- Renamed the installable package and CLI to `mermaid-marinetraffic` with the `winnow_gps` command.
- Defaulted CLI output to `$MERMAID/marinetraffic` when `-o/--output` is omitted.

## [0.1.2] - 2026-03-18

### Changed
- Output filename prefix is now `recent_gps_` instead of `last_50_gps_`.
- README was updated to document current input modes, defaults, and output naming.

### Added
- `AGENTS.md` now captures repo-level standing rules for future Codex threads.

## [0.1.1] - 2026-03-05

### Changed
- Output placemark datetime format is now `DD-Mon-YYYY HH:MM` (for both KML and SOM input flows).
- Output filename source separator uses a single underscore before source tag:
  - `last_50_gps_<STATION>_src-kml.kml`
  - `last_50_gps_<STATION>_src-som-all.kml`
- Script is now named `gps_winnower.py` in usage/docs.

## [0.1.0] - 2026-03-04

### Added
- Standalone `gps_winnower.py` CLI supporting:
  - single-file KML input mode
  - local batch directory mode (`-p`)
  - online SOM `_all.txt` mode (`--som-all`, `--som-url`)
- Last-N unique point selection (default `--limit 50`) with adjacent duplicate removal.
- Source-tagged output naming:
  - `last_50_gps_<STATION>_src-kml.kml`
  - `last_50_gps_<STATION>_src-som-all.kml`
- Embedded output provenance metadata (`source_type`, `source_ref`, `generated_utc`, `limit`).
- CLI version reporting via `--version`, sourced from `VERSION`.
