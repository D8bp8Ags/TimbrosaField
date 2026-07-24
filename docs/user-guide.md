# User Guide

TimbrosaField is a desktop application for reviewing, tagging, and exporting WAV
field recordings. The app is built around one workflow: open a folder of WAV
files, inspect recordings, add useful metadata and tags, then export the result
for analysis or Ableton Live.

## Who This Is For

Use TimbrosaField when you want to:

- Review field recordings visually and by listening.
- Store tags and metadata directly inside WAV files.
- Apply the same tags to multiple recordings.
- Export metadata for cataloging or spreadsheet work.
- Generate an Ableton Live project organized by tag category.

## First Start

Start the app from the repository root:

```bash
python3 -m my_app.main
```

If this is the first run, open **Edit > User Config** and review the default
metadata and folder locations.

## Basic Workflow

1. Open **File > Open Directory** or press `Ctrl+O`.
2. Choose a folder containing WAV files.
3. Select a file from the file list.
4. Inspect the waveform, playback, metadata, and cue information.
5. Add or edit tags and metadata.
6. Save the WAV metadata changes.
7. Repeat for the next file, or use batch tools for multiple files.
8. Export to CSV or Ableton Live when the folder is tagged.

## Main Menus

The application is organized around these menu groups:

| Menu | Main Use |
|---|---|
| **File** | Open/reload folders, batch import WAV files, export CSV/Ableton, open recent folders, quit. |
| **Edit** | User config, clear/reset tags, batch tagging, Photo GPS Matcher, template manager. |
| **View** | Waveform mode, zoom, metadata panel visibility, mouse label detail, theme. |
| **Audio** | Playback, stop, volume, mute. |
| **Analysis** | Analytics dashboard, cue point overview, AI analysis. |
| **Help** | Quick start, keyboard shortcuts, about dialog. |

## Opening Recordings

Use **File > Open Directory** to load a folder. TimbrosaField scans the selected
folder for WAV files and shows them in the file list.

Use **File > Reload Directory** or `F5` when files were added, removed, or edited
outside the app.

Recent directories are stored as local user configuration. They are not part of
the public project files.

## Batch Importing WAV Files

Use **File > Import/Export > Batch Import WAV Files** or `Ctrl+I` to import WAV
files into the configured field recording directory.

Use this when files are still on a recorder, temporary folder, or external drive
and you want to bring them into the working collection before tagging.

## Waveform and Playback

After selecting a WAV file, the app loads the waveform and metadata.

Common playback actions:

- Press `Space` to play or pause.
- Press `Escape` to stop playback.
- Use Left / Right arrow to seek backward or forward.
- Use `=` and `-` to adjust volume.
- Press `M` to mute or unmute.
- Click or drag in the waveform area to navigate visually.

For large files, the waveform view uses downsampling so navigation stays
responsive.

## Waveform Display and View Options

Use **View > Waveform Display** to choose how channels are shown:

- **Mono View**: show a single combined waveform.
- **Stereo View**: show stereo/per-channel information separately.
- **Overlay View**: overlay channels in one view.

Use the zoom controls to inspect details:

- **View > Zoom In** or `Ctrl+=`.
- **View > Zoom Out** or `Ctrl+-`.
- **View > Fit to Window** or `Ctrl+0`.

Use **View > Show/Hide Metadata Tables** or `Ctrl+T` to show or hide metadata
tables.

Use **View > Mouse Labels** to control how much information appears while moving
over the waveform:

- **Minimal**: fastest, least detail.
- **Performance**: balanced default.
- **Professional**: more detailed audio information.
- **Professional+**: most detail, including heavier analysis features.

Use **View > Theme** to switch between light, dark, macOS dark, and native macOS
styling.

## Metadata

TimbrosaField reads and writes standard WAV metadata, including INFO chunk fields
and BEXT/Broadcast Wave metadata when present.

Common INFO fields:

| Field | Meaning |
|---|---|
| `INAM` | Recording title. |
| `IART` | Artist or creator. |
| `ICRD` | Creation date. |
| `ISFT` | Software name. |
| `IENG` | Engineer or recordist. |
| `ICMT` | Comments. TimbrosaField uses this for tags. |

Default metadata can be configured in **Edit > User Config**.

## Saving Changes

When saving tag or metadata changes, the app can ask how the WAV should be
written.

Save options:

| Option | Meaning |
|---|---|
| Copy with `_edit` suffix | Safest option. Keeps the original unchanged. |
| Overwrite original | Writes directly over the current file. This is permanent. |
| Create `.bak` then replace original | Makes a backup file before replacing the original. |
| Custom name | Writes a new file with a chosen name. |

If the file already has tags, you can choose whether new tags should be added to
existing tags or replace them.

## Tags

Tags are stored in the WAV comment metadata field and are used throughout the app
for search, analysis, batch work, and Ableton export organization.

The tag system includes categories such as:

- Environment: forest, field, river, beach, street.
- Sound source: bird, traffic, voices, running water.
- Conditions: rain, wind, storm, fog.
- Time: morning, afternoon, evening, night.
- Sound character: quiet, loud, close, distant, continuous.
- Recording: mono, stereo, clean, noisy, distorted.
- Mood: calm, tense, dark, eerie.

Use the tag input and autocomplete suggestions to keep terminology consistent.

## Tag Templates

Templates are reusable groups of tags for common recording situations.

Use **Edit > Template Manager** or `F9` to manage templates.

Quick template shortcuts:

| Shortcut | Action |
|---|---|
| `Ctrl+1` | Apply template 1. |
| `Ctrl+2` | Apply template 2. |
| `Ctrl+3` | Apply template 3. |
| `Ctrl+4` | Apply template 4. |

Templates are stored as local user configuration.

## Clearing and Resetting Tags

Use **Edit > Clear Current Tags** or `Ctrl+Shift+C` to clear tags from the
currently selected recording.

Use **Edit > Reset to Defaults** or `Ctrl+Shift+R` to restore editable metadata
fields to the defaults configured in **User Config**.

## Batch Tagging

Use **Edit > Batch Tag Editor** or `Ctrl+B` to apply tags to multiple WAV files.

Typical batch workflow:

1. Open a directory with WAV files.
2. Open the batch tag editor.
3. Select the files you want to update.
4. Enter the tags to apply.
5. Choose whether to merge with existing tags or replace them.
6. Apply the changes.

Use merge when you want to add shared tags while keeping each file's existing
tags. Use replace only when the selected files should receive the same final tag
set.

The batch editor can create backup files before applying changes. Use backups for
important recordings or when applying changes to many files at once.

## Photo GPS Matcher

Use **Edit > Photo GPS Matcher** or `Ctrl+P` to match WAV recordings to photos by
timestamp and write GPS information into the WAV iXML metadata.

Typical workflow:

1. Open a folder of WAV recordings.
2. Open **Photo GPS Matcher**.
3. Choose a photo folder.
4. Set the time tolerance for matching photo timestamps to recording timestamps.
5. Scan for matches.
6. Review the table with WAV time, photo time, time difference, GPS status, and
   existing iXML status.
7. Optionally enable **Propagate GPS to unmatched files** to reuse nearby GPS
   data within a configured maximum time gap.
8. Keep **Create backup (.bak)** enabled unless you are intentionally writing
   without backups.
9. Apply GPS metadata.

Use **Remove iXML** when existing iXML GPS metadata should be removed from the
selected recordings.

## Analysis

TimbrosaField includes collection-level analysis tools.

Use **Analysis > Analytics Dashboard** or `Ctrl+A` to inspect:

- Total number of files.
- Total duration and file size.
- Most common tags.
- Audio specifications.
- Timeline and metadata-derived dates where available.

Use **Analysis > Cue Point Analysis** or `Ctrl+U` to inspect cue-point metadata
and markers in recordings.

The analytics dashboard contains overview, tags, audio, and timeline tabs. It
also includes an export report action for saving a text report of the analysis.

The cue point overview supports:

- Filtering by cue type.
- Showing or hiding files without cue points.
- Navigating to a selected cue in the main waveform/player.
- Exporting a cue list.

## AI Analysis

Use **Analysis > AI Analysis** to run available AI backends on the selected WAV
file. The dialog supports selecting enabled AI modules, starting analysis,
re-analyzing, managing models, filtering detections, selecting tags, and applying
selected AI-derived tags back to the recording workflow.

Main AI analysis areas:

- **AI modules**: choose which installed backends to run.
- **Start Analysis**: run analysis for the selected WAV.
- **Re-analyse**: clear cached results and run again.
- **Manage Models**: open the AI model manager.
- **Graph label**: choose scientific, English, or Dutch display labels.
- **Detections tab**: inspect detections by time, score, label, source, and
  enabled state.
- **Tags tab**: select suggested tags to apply.
- **Raw JSON tab**: inspect raw backend output.

The AI Model Manager can install, import, verify, retry, or delete supported model
assets. AI models are local runtime files and are not part of the public project
files.

## Exporting Metadata

Use **File > Export Metadata CSV** or `Ctrl+Shift+E` to export metadata for the
current directory.

The CSV export includes file information, WAV metadata, audio specs, cue-point
counts, tags, and status information for files that could not be processed.

Use CSV export when you want to review recordings in a spreadsheet, archive a
catalog, or share metadata without sharing the WAV files.

## Exporting to Ableton Live

Use **File > Export to Ableton Live** or `Ctrl+E` to generate an Ableton Live
project from the tagged recordings.

The export organizes recordings by tag category so recordings can be browsed by
subject or context inside Ableton.

Ableton export can use a local `default_template.als` file as a base template.
That file is local user data and is not included in the public repository by
default.

## User Configuration

Open **Edit > User Config** or press `Ctrl+,` to edit:

- Default WAV metadata values.
- Field recording directory.
- Ableton export directory.

Configuration is stored in the operating system's user-data location. Legacy
config files under the source tree may be read as a migration fallback, but new
user configuration should be treated as local user data.

## Help Inside the App

Use **Help > Help & Quick Start** or `Ctrl+Shift+?` for the in-app overview.

Use **Help > Keyboard Shortcuts** or `F1` for a shortcut reference.

Use **Help > About** or `F12` for application information.

## Keyboard Shortcuts

| Action | Shortcut |
|---|---|
| Open directory | `Ctrl+O` |
| Reload directory | `F5` |
| Batch import files | `Ctrl+I` |
| Export to Ableton | `Ctrl+E` |
| Export metadata CSV | `Ctrl+Shift+E` |
| Quit application | `Ctrl+Q` |
| Open user config | `Ctrl+,` |
| Template manager | `F9` |
| Batch tag editor | `Ctrl+B` |
| Photo GPS Matcher | `Ctrl+P` |
| Clear tags | `Ctrl+Shift+C` |
| Reset defaults | `Ctrl+Shift+R` |
| Apply template 1-4 | `Ctrl+1` - `Ctrl+4` |
| Zoom in / out | `Ctrl+=` / `Ctrl+-` |
| Fit waveform to window | `Ctrl+0` |
| Toggle metadata panel | `Ctrl+T` |
| Play / pause | `Space` |
| Stop playback | `Escape` |
| Seek backward / forward | Left / Right arrow |
| Volume up / down | `=` / `-` |
| Mute toggle | `M` |
| Analytics dashboard | `Ctrl+A` |
| Cue point analysis | `Ctrl+U` |
| Keyboard shortcuts help | `F1` |
| Help and quick start | `Ctrl+Shift+?` |
| About | `F12` |

## Good Practices

- Keep original recordings backed up before large batch edits.
- Use consistent tags rather than many near-duplicates.
- Review metadata after batch operations.
- Use CSV export as a lightweight catalog snapshot.
- Keep local configuration, WAV files, Ableton files, and screenshots with real
  data out of public project files.

## Troubleshooting

### The app cannot find `my_app`

Run the app from the repository root after installing the package in editable
mode:

```bash
pip install -e . --no-deps
python3 -m my_app.main
```

### A folder does not show expected files

Use **File > Reload Directory** or press `F5`. Confirm the files are WAV files
and are readable by the current user account.

### Metadata changes are not visible elsewhere

Save the file after editing. Some audio tools do not display all WAV INFO or BEXT
fields, even when the metadata is present in the file.

### Batch tagging changed more than expected

Check whether the batch editor used merge or replace mode. Restore from your own
backup if the wrong mode was applied.

### Ableton export does not use the expected template

Confirm that the local Ableton template exists and is compatible with the Ableton
version you use. Template files are local and are not included in the public
repository by default.
