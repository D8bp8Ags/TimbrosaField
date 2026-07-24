# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

project_root = Path.cwd()
resources_dir = project_root / "src" / "my_app" / "resources"

datas = [
    (str(resources_dir / "background.png"), "my_app/resources"),
    (str(resources_dir / "icon.png"), "my_app/resources"),
]

hiddenimports = [
    "my_app.resources",
    "my_app.ai.backends.ast_backend",
    "my_app.ai.backends.birdnet_backend",
    "my_app.ai.backends.perch_backend",
]

a = Analysis(
    ["src/my_app/main.py"],
    pathex=["src"],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="TimbrosaField",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(resources_dir / "icon.png"),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="TimbrosaField",
)
app = BUNDLE(
    coll,
    name="TimbrosaField.app",
    icon=str(resources_dir / "icon.png"),
    bundle_identifier="org.timbrosa.timbrosafield",
    info_plist={
        "CFBundleName": "TimbrosaField",
        "CFBundleDisplayName": "TimbrosaField",
        "CFBundleShortVersionString": "1.0.0",
        "CFBundleVersion": "1.0.0",
        "NSHighResolutionCapable": True,
    },
)
