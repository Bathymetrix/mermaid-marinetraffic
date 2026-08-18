# AGENTS.md

## Project scope

- `mermaid-marinetraffic` is an installable Python package with the public CLI form `mermaid-marinetraffic <command> [options]`.
- Command names are process-oriented. `winnow_gps` owns the existing GPS-winnowing behavior.
- Use Python 3.12 or later unless broader instructions require a specific runtime.
- Keep this a small standard-library package unless the task establishes a concrete need for a larger structure.

## Compatibility

- `winnow_gps_file` accepts exactly one local input source: `--kml FILE`, `--txt FILE`, or `--jsonl FILE`. `winnow_gps_dir` recursively processes the corresponding source family from one directory.
- Preserve established output filenames, placemark names, and KML provenance metadata unless a task explicitly changes them.
- Update `README.md` and focused tests when user-visible CLI or output behavior changes.

## Repository maintenance

- Keep `CHANGELOG.md` accurate; use an `Unreleased` section for unreleased changes rather than creating a version or rewriting released history.
- Keep package version metadata authoritative and available when installed.
- Do not stage, commit, amend, push, rebase, or otherwise modify Git history unless explicitly authorized.
- Use Git-aware moves and renames when appropriate.
