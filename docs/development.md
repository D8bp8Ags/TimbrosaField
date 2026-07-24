# Development Guide

## Requirements

- Python 3.11 or newer.
- Runtime, development, optional AI, and build dependencies from
  `pyproject.toml`.
- Build and tool configuration from `pyproject.toml`.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev,photo]"
```

Run all commands from the repository root.

Install optional AI backends only when you need them:

```bash
python -m pip install -e ".[ast,birdnet,perch]"
```

Use `python -m pip ...` after activating `.venv`; that keeps package
installation tied to the project-local environment.

## Run the Application

```bash
python -m my_app.main
```

Do not start `main.py` directly from inside `src/my_app/`; the app expects the
package import path provided by the editable install.

After installation, the GUI entrypoint is also available as:

```bash
timbrosa-field
```

## Tests

```bash
python -m pytest
```

For Qt/UI tests in headless environments:

```bash
QT_QPA_PLATFORM=offscreen python -m pytest
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

## Build a macOS App

TimbrosaField uses PyInstaller for local native app builds. The maintained build
configuration is:

```text
TimbrosaField_macos.spec
```

Build the macOS `.app` from the repository root:

```bash
python scripts/release/build_macos_app.py
```

The helper restarts itself with `.venv/bin/python` when it is launched from a
different Python environment, so activating `.venv` first is optional.

Check which command will run without building:

```bash
python scripts/release/build_macos_app.py --dry-run
```

This runs:

```bash
python -m PyInstaller --clean --noconfirm TimbrosaField_macos.spec
```

The app bundle is written to:

```text
dist/TimbrosaField.app
```

The bundle includes the Python app code and bundled UI resources from
`src/my_app/resources/`.

Local user data is not bundled:

- WAV recordings.
- Ableton templates and exported projects.
- User config under `src/my_app/config/` or the platform user-data directory.
- Downloaded AI models.
- Internal notes under `notes/`.

Optional AI backends may require extra dependencies and local model installation
before they work in a packaged app. Build and validate AI-enabled releases
separately from the base app build.

PyInstaller builds are platform-specific. Build macOS releases on macOS, Windows
releases on Windows, and Linux releases on Linux.
