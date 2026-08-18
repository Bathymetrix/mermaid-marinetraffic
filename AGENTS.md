# AGENTS.md

## Project scope

- `merinetraffic` is an installable Python package with the public CLI form `merinetraffic <command> [options]`.
- Command names are process-oriented. `winnow_gps` owns the existing GPS-winnowing behavior.
- Use Python 3.12 or later unless broader instructions require a specific runtime.
- Keep this a small standard-library package unless the task establishes a concrete need for a larger structure.

## Compatibility

- Preserve the three supported input modes: a single local KML file, local batch mode via `-p/--path`, and online SOM batch mode via `--som-all`.
- Preserve established output filenames, placemark names, and KML provenance metadata unless a task explicitly changes them.
- Update `README.md` and focused tests when user-visible CLI or output behavior changes.

## Repository maintenance

- Keep `CHANGELOG.md` accurate; use an `Unreleased` section for unreleased changes rather than creating a version or rewriting released history.
- Keep package version metadata authoritative and available when installed.
- Do not stage, commit, amend, push, rebase, or otherwise modify Git history unless explicitly authorized.
- Use Git-aware moves and renames when appropriate.
