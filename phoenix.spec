# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Phoenix Solutions — Blog Marketing Automation
# Build:  pyinstaller phoenix.spec --clean

block_cipher = None

a = Analysis(
    ['gui.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        # Read-only resource files bundled into the exe package
        ('Blogs/_new-post.html',            'Blogs'),
        ('Prompts',                          'Prompts'),
        ('MarketingSchedule/Calender.json',  'MarketingSchedule'),
    ],
    hiddenimports=[
        'tkinter',
        'tkinter.ttk',
        'tkinter.scrolledtext',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'groq',
        'requests',
        'dotenv',
        'apscheduler',
        'apscheduler.schedulers.blocking',
        'apscheduler.triggers.cron',
        'charset_normalizer',
        'certifi',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy', 'pandas', 'scipy', 'PIL', 'cv2'],
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
    name='PhoenixMarketing',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # No console window — GUI only
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='icon.ico',      # Uncomment and add icon.ico to enable custom icon
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PhoenixMarketing',
)
