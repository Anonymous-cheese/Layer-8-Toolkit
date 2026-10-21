# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['oui_offline.pyw'],
    pathex=[],
    binaries=[],
    datas=[('manuf', '.'), ('icon.ico', '.'),
           ('data/iana-service-names-port-numbers.csv', 'data'),
           ('THIRD_PARTY_NOTICES.txt', '.')],
    hiddenimports=[],
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
    a.binaries,
    a.datas,
    [],
    name='Layer 8 Toolkit',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icon.ico'],
)
