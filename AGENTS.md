# AGENTS.md

## Instruction sources

These instructions supplement:

- the global Codex AGENTS (`~/.codex/AGENTS.md`)
- the shared MERMAID AGENTS (`$MERMAID/AGENTS.md`)

Before beginning work, read and follow:

- `$MERMAID/AGENTS.md`

If you cannot locate, read, or understand the shared MERMAID AGENTS, stop and
tell the user before proceeding. Do not silently continue using only this file.

If instructions conflict, this file takes precedence.

## Project scope

- `mermaid-marinetraffic` is an installable Python package with the public CLI form `mermaid-marinetraffic <command> [options]`.
- Command names are process-oriented. `winnow_gps` owns the existing GPS-winnowing behavior.
- Use Python 3.12 or later unless broader instructions require a specific runtime.
- Keep this a small standard-library package unless the task establishes a concrete need for a larger structure.

## Compatibility

- Product commands are `trajectory`, `points`, and `polygon`.
- Input source options accept a file or recursively discovered directory input.
- Trajectory defaults to complete valid, adjacent-deduplicated history. `--limit` means most-recent unique GPS fixes.
- MarineTraffic KML must not exceed 400,000 serialized bytes. Never silently truncate oversized history; report the exact maximum fitting `--limit`.
- Generated KML files must contain exactly one geometry type because empirical MarineTraffic mixed-geometry imports have behaved inconsistently: trajectory is LineString-only, points is Point-only, and polygon is Polygon-only.
- Polygon uses a required kilometer radius and a 36-vertex geodesic ring plus its repeated closing coordinate. Source parsing and normalization are shared across products.
- Update `README.md` and focused tests when user-visible CLI or output behavior changes.

## Repository maintenance

- Keep `CHANGELOG.md` accurate; use an `Unreleased` section for unreleased changes rather than creating a version or rewriting released history.
- Keep package version metadata authoritative and available when installed.
- Bump the package version for externally visible behavior changes and record the change under `Unreleased`.
- Do not stage, commit, amend, push, rebase, or otherwise modify Git history unless explicitly authorized.
- Use Git-aware moves and renames when appropriate.
