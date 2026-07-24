# Development Guide

## Requirements

- Python 3.11 or newer.
- Runtime dependencies from `requirements.txt`.
- Build and tool configuration from `pyproject.toml`.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e . --no-deps
```

Run all commands from the repository root.

## Run the Application

```bash
python3 -m my_app.main
```

Do not start `main.py` directly from inside `src/my_app/`; the app expects the
package import path provided by the editable install.

## Tests

```bash
python3 -m pytest
```

For Qt/UI tests in headless environments:

```bash
QT_QPA_PLATFORM=offscreen python3 -m pytest
```

## Code Quality

- Keep changes scoped to the relevant package/module.
- Prefer existing helpers and patterns over new abstractions.
- Use logging instead of `print()` in application code.
- Keep slow WAV, file, AI, and export work off the main Qt thread.
- Use structured parsers and path APIs for JSON, TOML, WAV metadata, and paths.
- Keep public docstrings Google-style where required by linting.

## Local-Only Files

The repository uses a public allowlist. Local tool state, generated files, app
configuration, user media, private launchers, and internal notes are intentionally
ignored.
