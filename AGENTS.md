# AGENTS.md

## Project scope

- `mermaid-marinetraffic` is an installable Python package with the public CLI form `mermaid-marinetraffic <command> [options]`.
- Command names are process-oriented. `winnow_gps` owns the existing GPS-winnowing behavior.
- Use Python 3.12 or later unless broader instructions require a specific runtime.
- Keep this a small standard-library package unless the task establishes a concrete need for a larger structure.

## Compatibility

- `trajectory` is the primary product command; `points` retains individual Point output.
- Input source options accept a file or recursively discovered directory input.
- Trajectory defaults to complete valid, adjacent-deduplicated history. `--limit` means most-recent unique GPS fixes.
- MarineTraffic KML must not exceed 400,000 serialized bytes. Never silently truncate oversized history; report the exact maximum fitting `--limit`.
- Trajectory KML contains a chronological LineString and a separate latest Point when at least two fixes exist. Source parsing and selection rules must be shared by both renderers.
- Update `README.md` and focused tests when user-visible CLI or output behavior changes.

## Repository maintenance

- Keep `CHANGELOG.md` accurate; use an `Unreleased` section for unreleased changes rather than creating a version or rewriting released history.
- Keep package version metadata authoritative and available when installed.
- Do not stage, commit, amend, push, rebase, or otherwise modify Git history unless explicitly authorized.
- Use Git-aware moves and renames when appropriate.
