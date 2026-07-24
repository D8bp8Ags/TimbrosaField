# CLAUDE.md

Guidance for Claude Code and Claude-based coding agents working in this
repository.

## Project

TimbrosaField is a Python desktop application for analyzing, visualizing, tagging,
and exporting field recordings. Metadata is stored in WAV files, and the app can
generate Ableton Live project templates organized by tag category.

Use the current repository root as the working root. Do not depend on
machine-local absolute paths, generated mirror folders, IDE workspace state, or
local shell history.

## Repository layout

- `src/my_app/` contains application source code.
- `tests/` contains unit, integration, and UI tests.
- `docs/` contains maintained project documentation and public assets.
- `scripts/data_tools/` contains data-maintenance utilities.
- `scripts/diagnostics/` contains diagnostic and runtime investigation scripts.
- `scripts/experimental/` contains exploratory code that should not be treated as
  stable product behavior.
- `TASKS.md` is a local working task list and may contain publication/privacy
  notes.

## Standard commands

Run commands from the repository root unless a task explicitly says otherwise.

- Install runtime dependencies: `pip install -r requirements.txt`
- Install the package for local development: `pip install -e . --no-deps`
- Run the application: `python3 -m my_app.main`
- Run all tests: `python3 -m pytest`
- Run Qt/UI tests headlessly: `QT_QPA_PLATFORM=offscreen python3 -m pytest`
- Use the formatting and linting configuration in `pyproject.toml`.

## Working rules

- Make small, targeted changes that fit the existing structure.
- Read surrounding code before editing; prefer existing helpers and patterns.
- Keep Qt UI responsive by moving slow file, WAV, AI, and export work off the main
  thread.
- Use structured libraries for WAV metadata, JSON, TOML, and paths.
- Use logging in application code instead of `print()`.
- Keep public docstrings Google-style where required by the lint configuration.

## Tests

- Update tests when behavior changes, especially for WAV metadata mutation,
  exports, configuration paths, AI integration contracts, and public UI flows.
- Prefer focused tests close to the changed behavior.
- For GUI tests, use the existing test patterns and run with
  `QT_QPA_PLATFORM=offscreen` when appropriate.
- If tests cannot be run, report exactly what was not run and why.

## Documentation

- Keep `README.md` user-facing and concise.
- Keep durable technical documentation under `docs/`.
- Mark documents as current, experimental, deprecated, or archival when useful.
- Do not preserve stale audit notes in public docs unless they are intentionally
  moved to an archive with context.

## Privacy

- Do not write absolute local paths, usernames, private recording names, export
  folders, model cache paths, tokens, secrets, or machine-specific configuration
  into tracked files.
- Treat local IDE/tool settings and app config files as private unless the user
  explicitly requests a sanitized public version.
- Check public screenshots and documentation for personal details before
  publishing.

## Git safety

- Preserve user edits and unrelated changes.
- Do not run destructive git or filesystem operations unless explicitly asked.
- Keep commits narrowly scoped and explain functional changes clearly.
