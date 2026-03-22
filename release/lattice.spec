# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for building the lattice CLI as a standalone binary.

Run from the repository root:
    pyinstaller release/lattice.spec

The binary lands in dist/lattice (or dist/lattice.exe on Windows).
"""

import sys
from pathlib import Path

block_cipher = None

ROOT = Path(SPECPATH).parent  # repo root

a = Analysis(
    [str(ROOT / "release" / "entry.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[],
    hiddenimports=[
        "lattice",
        "lattice.cli",
        "lattice.cli.main",
        "lattice.runtime",
        "lattice.runtime.engine",
        "lattice.runtime.registry",
        "lattice.audit",
        "lattice.audit.trail",
        "lattice.auth",
        "lattice.auth.scopes",
        "lattice.discovery",
        "lattice.discovery.openapi",
        "lattice.discovery.inventory",
        "lattice.failure",
        "lattice.failure.retry",
        "lattice.failure.policies",
        "lattice.human",
        "lattice.human.task",
        "lattice.human.gaps",
        "lattice.llm",
        "lattice.llm.provider",
        "lattice.llm.prompts",
        "lattice.capability",
        "lattice.context",
        "lattice.errors",
        "lattice.intent",
        "lattice.projection",
        "lattice.state",
        "lattice.step",
        "lattice.types",
        "click",
        "yaml",
        "rich",
        "rich.console",
        "rich.table",
        "rich.tree",
        "rich.panel",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="lattice",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
