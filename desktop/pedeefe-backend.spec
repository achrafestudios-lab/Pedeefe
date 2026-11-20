# -*- mode: python ; coding: utf-8 -*-
"""Especificación PyInstaller del backend de Pedeefe Desktop (v1.7).

Construir desde desktop/:

    .venv/bin/python -m PyInstaller --noconfirm --clean \
        --distpath backend-dist --workpath build pedeefe-backend.spec

El ejecutable resultante se copia a resources/backend dentro del paquete
Electron (ver package.json -> build.extraResources).
"""

from pathlib import Path

spec_dir = Path(SPECPATH)
root = spec_dir.parent

block_cipher = None

a = Analysis(
    [str(spec_dir / "launcher.py")],
    pathex=[str(root), str(spec_dir)],
    binaries=[],
    datas=[
        (str(root / "app.py"), "."),
        (str(root / "templates"), "templates"),
        (str(root / "static"), "static"),
    ],
    hiddenimports=[
        "app",
        "pikepdf",
        "fitz",
        "pymupdf",
        "pytesseract",
        "pdf2docx",
        "pdf2image",
        "pdfplumber",
        "weasyprint",
        "docx",
        "pptx",
        "openpyxl",
        "reportlab",
        "PIL",
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
    name="pedeefe-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
