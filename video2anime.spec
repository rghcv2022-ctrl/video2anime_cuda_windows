# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

project_dir = Path.cwd()
hooks_dir = project_dir / 'hooks'

hiddenimports = [
    'imageio_ffmpeg',
    'imageio_ffmpeg.binaries',
]

datas = []
datas += collect_data_files('imageio_ffmpeg', subdir='binaries')

# Runtime packages (onnxruntime-gpu / nvidia-cudnn-cu11) are downloaded on first launch
# into %LOCALAPPDATA%/Video2AnimeCUDA/runtime/py39/site-packages and are NOT bundled here.
a = Analysis(
    ['app.py'],
    pathex=[str(project_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[str(hooks_dir)],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'onnxruntime',
        'onnxruntime.capi',
        'onnxruntime.datasets',
        'onnxruntime.tools',
        'onnxruntime.transformers',
        'onnxruntime.quantization',
        'onnxruntime.backend',
        'nvidia',
        'torch',
        'torchvision',
        'torchaudio',
        'tensorflow',
        'keras',
        'matplotlib',
        'pandas',
        'scipy',
        'sklearn',
        'PyQt5',
        'PyQt6',
        'PySide2',
        'PySide6',
        'IPython',
        'notebook',
        'jupyter',
        'nbconvert',
        'nbformat',
        'jsonschema',
        'openpyxl',
        'lxml',
        'tables',
        'sqlalchemy',
        'pytest',
        'sphinx',
        'docutils',
        'botocore',
        'boto3',
        'qtpy',
        'pygame',
    ],
    noarchive=True,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Video2AnimeCUDA',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Video2AnimeCUDA',
)
