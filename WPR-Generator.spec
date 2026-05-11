# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the WPR Generator Windows EXE.

Run:
    pyinstaller --noconfirm WPR-Generator.spec

Produces dist/WPR-Generator/ — copy or zip the whole folder; double-click
WPR-Generator.exe inside it to run.
"""
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

block_cipher = None

# Streamlit ships a lot of runtime data (static/, runtime/) and uses dynamic
# imports — collect_all is the safest way to grab everything.
streamlit_datas, streamlit_binaries, streamlit_hiddenimports = collect_all("streamlit")
altair_datas, altair_binaries, altair_hiddenimports = collect_all("altair")
pptx_datas, pptx_binaries, pptx_hiddenimports = collect_all("pptx")
fitz_datas, fitz_binaries, fitz_hiddenimports = collect_all("fitz")  # PyMuPDF
pil_datas, pil_binaries, pil_hiddenimports = collect_all("PIL")

extra_datas = [
    ("app.py", "."),
    ("assets", "assets"),
    ("builder", "builder"),
    ("extractors", "extractors"),
]

hidden = [
    "streamlit",
    "streamlit.web.cli",
    "streamlit.web.bootstrap",
    "streamlit.runtime",
    "streamlit.runtime.scriptrunner.magic_funcs",
    "streamlit.runtime.scriptrunner.script_runner",
    "streamlit.runtime.scriptrunner.script_run_context",
    "streamlit.runtime.caching",
    "streamlit.runtime.caching.cache_data_api",
    "streamlit.runtime.caching.cache_resource_api",
    "streamlit.runtime.legacy_caching.caching",
    "streamlit.runtime.state",
    "streamlit.runtime.state.session_state_proxy",
    "streamlit.runtime.uploaded_file_manager",
    "streamlit.elements",
    "streamlit.components.v1",
    "streamlit.web.server",
    # Project modules
    "builder",
    "builder.build",
    "builder.design",
    "builder.defaults",
    "builder.state",
    "builder.slides",
    "builder.slides.activities",
    "builder.slides.aoc",
    "builder.slides.cover",
    "builder.slides.manpower",
    "builder.slides.photos",
    "builder.slides.programme",
    "builder.slides.quality",
    "extractors",
    "extractors.dcr",
    "extractors.logs",
] + streamlit_hiddenimports + altair_hiddenimports + pptx_hiddenimports + fitz_hiddenimports + pil_hiddenimports

a = Analysis(
    ["launcher.py"],
    pathex=["."],
    binaries=streamlit_binaries + altair_binaries + pptx_binaries + fitz_binaries + pil_binaries,
    datas=extra_datas + streamlit_datas + altair_datas + pptx_datas + fitz_datas + pil_datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
        "IPython",
        "jupyter",
        "notebook",
        "torch",
        "tensorflow",
        "pdfplumber",
        "pdfminer",
        "pdfminer.six",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="WPR-Generator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,  # keep console for first run; flip to False once verified
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="WPR-Generator",
)
