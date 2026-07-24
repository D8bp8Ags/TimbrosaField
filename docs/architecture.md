# Architecture Notes

TimbrosaField keeps runtime code under `src/my_app`, with separate packages for
audio playback, WAV metadata handling, UI, analysis, tags, AI integration, export,
and file management.

## Main Packages

| Path | Responsibility |
|---|---|
| `src/my_app/main.py` | Application entry point. |
| `src/my_app/ui/` | Main window, menus, settings, dialogs, and waveform UI. |
| `src/my_app/audio/` | Playback-related behavior. |
| `src/my_app/wav/` | WAV analysis and metadata save strategies. |
| `src/my_app/analysis/` | Waveform inspection and clipping logic. |
| `src/my_app/tags/` | Tag definitions, templates, and tag UI. |
| `src/my_app/export/` | CSV/Ableton export workflows. |
| `src/my_app/files/` | Directory loading and recent-directory behavior. |
| `src/my_app/ai/` | AI backend contracts, registry, model management, and UI. |
| `src/my_app/resources/` | Bundled runtime assets such as icons and backgrounds. |

## Runtime Data

Editable user configuration is runtime data, not source code. The app resolves
user config through platform-appropriate user-data paths and keeps the legacy
`src/my_app/config/` location as a read fallback only.

Do not commit user config, local recording folders, generated exports, downloaded
AI models, or machine-specific paths.

## Tests and Scripts

- `tests/` contains public unit, integration, and UI tests.
- `scripts/data_tools/` contains reproducible data-maintenance helpers.
- `scripts/diagnostics/` contains diagnostic scripts for local/runtime checks.
- `scripts/experimental/` contains exploratory code and should not define stable
  product behavior.
