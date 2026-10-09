# -*- mode: python ; coding: utf-8 -*-
# Spec exe portabile one-file + icona + splash screen nativo istantaneo.
# Metti icon.ico e splash.png nella stessa cartella di questo .spec (PC/)
#   pyinstaller --noconfirm --clean AirFlowTrace.spec

import os
from PyInstaller.building.splash import Splash
from PyInstaller.utils.hooks import collect_all

# Directory dello .spec = cartella PC/
try:
    SPECDIR = os.path.dirname(os.path.abspath(SPEC))
except NameError:
    SPECDIR = os.path.abspath(os.getcwd())

# Cerca icona (path ASSOLUTO)
_ICON_CANDIDATES = [
    os.path.join(SPECDIR, 'icon.ico'),
    os.path.join(SPECDIR, 'app.ico'),
    os.path.join(SPECDIR, 'AirFlowTrace.ico'),
    os.path.join(os.getcwd(), 'icon.ico'),
]
ICON = None
for p in _ICON_CANDIDATES:
    if os.path.isfile(p):
        ICON = os.path.abspath(p)
        break

# Cerca splash screen (path ASSOLUTO)
_SPLASH_CANDIDATES = [
    os.path.join(SPECDIR, 'splash.jpg'),
    os.path.join(os.getcwd(), 'splash.jpg'),
]
SPLASH = None
for p in _SPLASH_CANDIDATES:
    if os.path.isfile(p):
        SPLASH = os.path.abspath(p)
        break

print('=' * 50)
print('[spec] SPECDIR =', SPECDIR)
print('[spec] cwd     =', os.getcwd())

if ICON:
    size = os.path.getsize(ICON)
    print(f'[spec] ICONA OK: {ICON}  ({size} bytes)')
    if size < 100:
        print('[spec] ATTENZIONE: file .ico sospetto (troppo piccolo)')
else:
    print('[spec] NESSUNA ICONA trovata!')
    print('[spec] Cercati:', _ICON_CANDIDATES)

if SPLASH:
    size = os.path.getsize(SPLASH)
    print(f'[spec] SPLASH OK: {SPLASH}  ({size} bytes)')
else:
    print('[spec] NESSUN SPLASH SCREEN trovato (splash.png)!')
    print('[spec] Cercati:', _SPLASH_CANDIDATES)
print('=' * 50)

# Raccolta moduli pesanti
pg_datas, pg_binaries, pg_hidden = collect_all('pyqtgraph')
rl_datas, rl_binaries, rl_hidden = collect_all('reportlab')
pil_datas, pil_binaries, pil_hidden = collect_all('PIL')

hiddenimports = list(set(
    pg_hidden + rl_hidden + pil_hidden + [
        'plot_panel', 'ui_components', 'ReadSerial', 'config', 'export_pdf',
        'serial', 'serial.tools', 'serial.tools.list_ports',
        'pyqtgraph',
        'pyqtgraph.graphicsItems',
        'pyqtgraph.graphicsItems.PlotDataItem',
        'pyqtgraph.graphicsItems.InfiniteLine',
        'pyqtgraph.graphicsItems.LinearRegionItem',
        'pyqtgraph.graphicsItems.DateAxisItem',
        'numpy',
        'reportlab', 'reportlab.lib', 'reportlab.lib.pagesizes',
        'reportlab.lib.colors', 'reportlab.lib.styles',
        'reportlab.lib.units', 'reportlab.platypus',
        'PyQt6', 'PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets', 'PyQt6.sip',
    ]
))

# Inclusione dati extra
extra_datas = []
if ICON:
    extra_datas.append((ICON, '.'))
if SPLASH:
    extra_datas.append((SPLASH, '.'))

a = Analysis(
    [os.path.join(SPECDIR, 'main.py')],
    pathex=[SPECDIR],
    binaries=pg_binaries + rl_binaries + pil_binaries,
    datas=pg_datas + rl_datas + pil_datas + extra_datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy', 'IPython', 'jupyter'],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

# Configurazione dello Splash Screen Nativo del bootloader (apparizione immediata)
splash_target = None
if SPLASH:
    splash_target = Splash(
        SPLASH,
        binaries=a.binaries,
        datas=a.datas,
        text_pos=None,  # Nasconde il testo standard del bootloader per un design pulito
    )

exe = EXE(
    pyz,
    a.scripts,
    splash_target,                                    # <-- Attiva lo splash screen nativo
    splash_target.binaries if splash_target else [],  # <-- Dipendenze dello splash
    a.binaries,
    a.datas,
    [],
    name='AirFlowTrace',
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
    icon=ICON,
)