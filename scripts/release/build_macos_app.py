"""Build the TimbrosaField macOS app bundle with PyInstaller."""

from __future__ import annotations

import argparse
import platform
import subprocess
import sys
from pathlib import Path

FORBIDDEN_BUNDLE_FILENAMES = {
    "recent_directories.json",
    "tag_templates.json",
    "user_config.json",
}


def _project_venv_python(project_root: Path) -> Path:
    if platform.system() == "Windows":
        return project_root / ".venv" / "Scripts" / "python.exe"
    return project_root / ".venv" / "bin" / "python"


def _ensure_project_python(project_root: Path) -> int | None:
    """Restart this script with the project-local .venv Python when needed."""
    venv_python = _project_venv_python(project_root)
    current_python = Path(sys.executable).resolve()

    if current_python == venv_python.resolve():
        return None

    if not venv_python.exists():
        print(f"Missing project environment: {venv_python}")
        print("Create it from the repository root:")
        print("  python -m venv .venv")
        print("  .venv/bin/python -m pip install -e \".[dev,photo]\"")
        return 2

    command = [str(venv_python), str(Path(__file__).resolve()), *sys.argv[1:]]
    print(f"Restarting with project Python: {venv_python}", flush=True)
    return subprocess.call(command, cwd=project_root)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the TimbrosaField macOS .app with PyInstaller.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the PyInstaller command without building the app",
    )
    return parser.parse_args()


def _check_no_private_config_in_bundle(project_root: Path) -> int:
    """Fail the release if local user config JSONs were bundled."""
    bundle_root = project_root / "dist" / "TimbrosaField.app"
    if not bundle_root.exists():
        print(f"Missing app bundle after build: {bundle_root}")
        return 2

    matches = [
        path
        for path in bundle_root.rglob("*")
        if path.is_file() and path.name in FORBIDDEN_BUNDLE_FILENAMES
    ]
    if not matches:
        print("Release privacy check OK: no user config JSONs in app bundle.")
        return 0

    print("Release privacy check failed: user config JSONs found in app bundle.")
    for path in matches:
        print(f"  {path.relative_to(project_root)}")
    return 3


def main() -> int:
    """Run the local macOS app build."""
    args = _parse_args()
    project_root = Path(__file__).resolve().parents[2]
    spec_path = project_root / "TimbrosaField_macos.spec"

    if platform.system() != "Darwin":
        print("This release helper builds the macOS .app and must run on macOS.")
        return 2

    if not spec_path.exists():
        print(f"Missing spec file: {spec_path}")
        return 2

    restart_code = _ensure_project_python(project_root)
    if restart_code is not None:
        return restart_code

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        str(spec_path),
    ]
    if args.dry_run:
        print("PyInstaller command:")
        print(" ".join(command))
        return 0

    print("Building TimbrosaField.app with PyInstaller...")
    print(" ".join(command))
    build_code = subprocess.call(command, cwd=project_root)
    if build_code != 0:
        return build_code
    return _check_no_private_config_in_bundle(project_root)


if __name__ == "__main__":
    raise SystemExit(main())
