# TimbrosaField

TimbrosaField is a Python desktop application for analyzing, visualizing, tagging,
and exporting field recordings. It stores metadata directly inside WAV files and
can generate Ableton Live project templates organized by tag category.

## Features

- Waveform display with dynamic downsampling for large WAV files.
- Mono and stereo support with per-channel views.
- Clipping detection and cue point markers.
- Built-in audio player with seek and volume controls.
- INFO chunk and BEXT metadata reading/writing.
- Tag templates, tag auto-completion, batch tagging, and analytics.
- CSV export, JSON tag backup, and Ableton Live export.

## Requirements

- Python 3.11 or newer.
- Dependencies: `PyQt5`, `soundfile`, `numpy`, `pyqtgraph`.

## Installation

```bash
git clone https://github.com/D8bp8Ags/TimbrosaField.git
cd TimbrosaField

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

python -m pip install --upgrade pip
python -m pip install -e ".[dev,photo]"
python -m my_app.main
```

Run commands from the repository root. `my_app` is a package under `src/`, so
starting `main.py` directly from inside `src/my_app/` is not supported.

Optional AI backends can be installed into the same `.venv`:

```bash
python -m pip install -e ".[ast,birdnet,perch]"
```

## Documentation

- [Documentation index](docs/index.md)
- [User guide](docs/user-guide.md)
- [Development guide](docs/development.md)
- [Architecture notes](docs/architecture.md)

## Project Structure

```text
TimbrosaField/
  src/my_app/       # application source
  scripts/          # public maintenance and diagnostic scripts
  tests/            # public test suite
  docs/             # public markdown documentation
  pyproject.toml    # build metadata and tool configuration
```

## License

Licensed under the [GNU General Public License v3.0](LICENSE).
