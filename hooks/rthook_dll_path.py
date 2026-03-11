import os
import sys
from pathlib import Path

_DLL_DIR_HANDLES = []

if os.name == 'nt':
    base = Path(getattr(sys, '_MEIPASS', Path(sys.executable).resolve().parent))
    candidates = [
        base / 'onnxruntime' / 'capi',
        base / '_internal' / 'onnxruntime' / 'capi',
        base / 'nvidia' / 'cudnn' / 'bin',
        base / '_internal' / 'nvidia' / 'cudnn' / 'bin',
        base / 'nvidia' / 'cublas' / 'bin',
        base / '_internal' / 'nvidia' / 'cublas' / 'bin',
        base / 'nvidia' / 'cuda_runtime' / 'bin',
        base / '_internal' / 'nvidia' / 'cuda_runtime' / 'bin',
        base / 'cv2',
        base / '_internal' / 'cv2',
        base,
        base / '_internal',
    ]

    existing = []
    for d in candidates:
        if d.exists():
            try:
                if hasattr(os, 'add_dll_directory'):
                    handle = os.add_dll_directory(str(d))
                    _DLL_DIR_HANDLES.append(handle)
            except Exception:
                pass
            existing.append(str(d))

    if existing:
        current = os.environ.get('PATH', '')
        prepend = [p for p in existing if p not in current]
        if prepend:
            os.environ['PATH'] = os.pathsep.join(prepend + [current])
