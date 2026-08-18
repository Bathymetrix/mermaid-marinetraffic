# AGENTS.md

## Project scope

- `gps_winnower.py` is the main script entrypoint.
- Use Python 3.12 or later unless broader instructions require a specific runtime.
- Keep this a small, standard-library single-script utility unless the task establishes a concrete need for a larger structure.

## Compatibility

- Preserve the three supported input modes: a single local KML file, local batch mode via `-p/--path`, and online SOM batch mode via `--som-all`.
- Preserve established output filenames, placemark names, and KML provenance metadata unless a task explicitly changes them.
- Keep `README.md` synchronized with user-visible CLI behavior, defaults, filenames, and input modes.

## Repository maintenance

- Keep `CHANGELOG.md` accurate; use an `Unreleased` section for unreleased changes rather than creating a version or rewriting released history.
- Do not change `VERSION` unless explicitly asked.
- Do not stage, commit, amend, push, rebase, or otherwise modify Git history unless explicitly authorized.
- Use Git-aware moves and renames when appropriate.
