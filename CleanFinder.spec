# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['CleanFinder.py'],
    pathex=[],
    binaries=[],
    datas=[('resources', 'resources')],
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
    [],
    exclude_binaries=True,
    name='CleanFinder',
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
    icon=['resources/black_binder.icns'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='CleanFinder',
)
app = BUNDLE(
    coll,
    name='CleanFinder.app',
    icon='resources/black_binder.icns',
    bundle_identifier=None,
    info_plist={
        # "Open in CleanFinder" macOS Service. Handled at runtime by
        # src/non_ui_components/macos_services.py (NSMessage 'openInCleanFinder').
        'NSServices': [
            {
                'NSMenuItem': {'default': 'Open in CleanFinder'},
                'NSMessage': 'openInCleanFinder',
                'NSPortName': 'CleanFinder',
                'NSSendTypes': ['public.file-url', 'NSFilenamesPboardType'],
            }
        ],
    },
)
