from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Callable, Optional

import requests

LogFn = Optional[Callable[[str], None]]

RUNTIME_WHEELS = [
    {
        "slug": "onnxruntime-gpu",
        "filename": "onnxruntime_gpu-1.18.1-cp39-cp39-win_amd64.whl",
        "url": "https://files.pythonhosted.org/packages/3a/2e/1e254840ceda53e75a69f05d5e0f7937652f3b59346a1f0b19dd44c3b9c7/onnxruntime_gpu-1.18.1-cp39-cp39-win_amd64.whl",
        "sha256": "126035cd623445f9922ca0f277cf18ffc83d7e073c0c5c8057eee37f22e24440",
    },
    {
        "slug": "nvidia-cudnn-cu11",
        "filename": "nvidia_cudnn_cu11-8.9.5.29-py3-none-win_amd64.whl",
        "url": "https://files.pythonhosted.org/packages/b3/f5/97140674634a5a4f44387677bb8e5b75f72ea81ca108875f1a81854b3367/nvidia_cudnn_cu11-8.9.5.29-py3-none-win_amd64.whl",
        "sha256": "ba6358cafcbf9ab66887099f5c821dde3968d7b4580cb87c56b548947917b54d",
    },
]


def _default_log(_: str) -> None:
    pass


def get_app_base_dir() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Video2AnimeCUDA"


def get_runtime_root() -> Path:
    py_tag = f"py{sys.version_info.major}{sys.version_info.minor}"
    return get_app_base_dir() / "runtime" / py_tag


def get_runtime_site_packages() -> Path:
    return get_runtime_root() / "site-packages"


def get_runtime_wheels_dir() -> Path:
    return get_runtime_root() / "wheels"


def get_runtime_manifest_path() -> Path:
    return get_runtime_root() / "runtime_manifest.json"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _download(url: str, target: Path, expected_sha256: str, log_fn: LogFn = None) -> None:
    log = log_fn or _default_log
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".part")

    with requests.get(url, stream=True, timeout=120) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", "0"))
        written = 0
        h = hashlib.sha256()
        with tmp.open("wb") as fh:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                fh.write(chunk)
                h.update(chunk)
                written += len(chunk)
                if total:
                    pct = written / total * 100
                    log(f"Downloading runtime... {target.name} {pct:.1f}%")

    actual = h.hexdigest()
    if actual != expected_sha256:
        try:
            tmp.unlink(missing_ok=True)
        except TypeError:
            if tmp.exists():
                tmp.unlink()
        raise RuntimeError(f"Checksum mismatch for {target.name}: {actual} != {expected_sha256}")

    tmp.replace(target)


def _runtime_is_ready(site_packages: Path, manifest_path: Path) -> bool:
    if not manifest_path.exists():
        return False
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return False

    expected = {item["filename"]: item["sha256"] for item in RUNTIME_WHEELS}
    if manifest.get("wheels") != expected:
        return False

    checks = [
        site_packages / "onnxruntime" / "capi" / "onnxruntime_pybind11_state.pyd",
        site_packages / "onnxruntime" / "capi" / "onnxruntime_providers_cuda.dll",
        site_packages / "nvidia" / "cudnn" / "bin" / "cudnn64_8.dll",
    ]
    return all(p.exists() for p in checks)


def ensure_runtime(log_fn: LogFn = None) -> Path:
    log = log_fn or _default_log
    root = get_runtime_root()
    site_packages = get_runtime_site_packages()
    wheels_dir = get_runtime_wheels_dir()
    manifest_path = get_runtime_manifest_path()

    root.mkdir(parents=True, exist_ok=True)
    wheels_dir.mkdir(parents=True, exist_ok=True)

    if _runtime_is_ready(site_packages, manifest_path):
        os.environ["VIDEO2ANIME_RUNTIME_SITEPACKAGES"] = str(site_packages)
        return site_packages

    log("Preparing local runtime cache (first launch may take a while)...")

    if site_packages.exists():
        shutil.rmtree(site_packages, ignore_errors=True)
    site_packages.mkdir(parents=True, exist_ok=True)

    manifest = {"wheels": {}}
    for item in RUNTIME_WHEELS:
        wheel_path = wheels_dir / item["filename"]
        if not wheel_path.exists() or _sha256(wheel_path) != item["sha256"]:
            log(f"Fetching runtime package: {item['slug']}")
            _download(item["url"], wheel_path, item["sha256"], log)
        else:
            log(f"Using cached runtime package: {item['filename']}")

        log(f"Extracting runtime package: {item['filename']}")
        with zipfile.ZipFile(wheel_path) as zf:
            zf.extractall(site_packages)
        manifest["wheels"][item["filename"]] = item["sha256"]

    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    os.environ["VIDEO2ANIME_RUNTIME_SITEPACKAGES"] = str(site_packages)
    return site_packages


def ensure_runtime_on_sys_path(log_fn: LogFn = None) -> Path:
    site_packages = ensure_runtime(log_fn)
    site_packages_str = str(site_packages)
    if site_packages_str not in sys.path:
        sys.path.insert(0, site_packages_str)
    os.environ["VIDEO2ANIME_RUNTIME_SITEPACKAGES"] = site_packages_str
    return site_packages
