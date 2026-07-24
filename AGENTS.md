# AGENTS.md

Guidance for Codex and other coding agents working in this repository.

## Project

TimbrosaField is a Python desktop application for analyzing, visualizing, tagging,
and exporting field recordings. Metadata is stored in WAV files, and the app can
generate Ableton Live project templates organized by tag category.

Treat the repository root as the source of truth. Do not rely on machine-local
absolute paths, IDE state, shell history, or generated mirror directories.

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

## Development commands

Run commands from the repository root unless a task explicitly says otherwise.

- Create and activate a project-local environment: `python -m venv .venv`
- Install local development dependencies: `python -m pip install -e ".[dev,photo]"`
- Install optional AI backends only when needed:
  `python -m pip install -e ".[ast,birdnet,perch]"`
- Run the application: `python -m my_app.main`
- Run tests: `python -m pytest`
- Run tests for Qt/UI code in headless environments:
  `QT_QPA_PLATFORM=offscreen python -m pytest`
- Lint/format using the settings in `pyproject.toml`.

## Coding standards

- Prefer small, targeted changes that match the existing package structure.
- Keep GUI work responsive; move slow file, WAV, AI, and export operations off the
  main Qt thread.
- Use structured APIs for WAV metadata, JSON, TOML, and path handling instead of
  ad hoc string manipulation.
- Use logging rather than `print()` in application code.
- Keep public docstrings Google-style where they already exist or are required by
  linting.
- Do not commit cache/build artifacts such as `__pycache__/`, generated exports,
  local model downloads, or IDE state.

## Testing expectations

- Add or update focused tests when changing parsing, WAV metadata mutation, export
  behavior, configuration paths, or public UI workflows.
- For UI startup or Qt behavior, prefer existing UI tests and run with
  `QT_QPA_PLATFORM=offscreen` when needed.
- If a test cannot be run locally, state the reason and the remaining risk.

## Documentation standards

- Keep `README.md` as the user-facing entry point.
- Keep durable technical notes under `docs/`.
- Prefer short, maintained documents over scattered historical notes.
- Documentation should clearly indicate whether it is current, experimental, or
  archival.
- Avoid publishing machine-local audit notes, personal paths, private media names,
  or unsanitized screenshots.

## Privacy and publication

- Do not add absolute local paths, usernames, private recording names, export
  folders, local model paths, API keys, tokens, or machine-specific configuration
  to tracked files.
- Treat files under local config, IDE, and tool settings directories as private
  unless the user explicitly asks to publish a sanitized version.
- Before changing public documentation or screenshots, check for personal details
  and user data.

## Git safety

- Preserve user changes. Do not revert or rewrite work you did not create unless
  explicitly asked.
- Avoid destructive commands unless the user clearly requested them.
- Keep commits scoped and describe user-visible behavior, not internal tool steps.
