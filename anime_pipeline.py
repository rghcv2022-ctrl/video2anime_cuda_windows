from __future__ import annotations

import ctypes
import json
import os
import shutil
import site
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Union

import cv2
import imageio_ffmpeg
import numpy as np
import requests

from runtime_manager import ensure_runtime_on_sys_path


STYLE_MODELS = {
    "hayao": {
        "label": "Hayao (default anime look)",
        "filename": "AnimeGANv2_Hayao.onnx",
        "url": "https://huggingface.co/vumichien/AnimeGANv2_Hayao/resolve/main/AnimeGANv2_Hayao.onnx",
    },
    "paprika": {
        "label": "Paprika (warmer colors)",
        "filename": "AnimeGANv2_Paprika.onnx",
        "url": "https://huggingface.co/vumichien/AnimeGANv2_Paprika/resolve/main/AnimeGANv2_Paprika.onnx",
    },
    "shinkai": {
        "label": "Shinkai (clean / cinematic)",
        "filename": "AnimeGANv2_Shinkai.onnx",
        "url": "https://huggingface.co/vumichien/AnimeGANv2_Shinkai/resolve/main/AnimeGANv2_Shinkai.onnx",
    },
}

LogFn = Optional[Callable[[str], None]]
ProgressFn = Optional[Callable[[float, str], None]]


def _default_log(_: str) -> None:
    pass


def _candidate_windows_gpu_dirs() -> list[Path]:
    dirs: list[Path] = []

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        base = Path(meipass)
        dirs.extend(
            [
                base / "onnxruntime" / "capi",
                base / "nvidia" / "cudnn" / "bin",
                base / "nvidia" / "cublas" / "bin",
                base / "nvidia" / "cuda_runtime" / "bin",
                base / "cv2",
                base,
            ]
        )

    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        internal_dir = exe_dir / "_internal"
        dirs.extend(
            [
                internal_dir / "onnxruntime" / "capi",
                internal_dir / "nvidia" / "cudnn" / "bin",
                internal_dir / "nvidia" / "cublas" / "bin",
                internal_dir / "nvidia" / "cuda_runtime" / "bin",
                internal_dir / "cv2",
                internal_dir,
                exe_dir,
            ]
        )

    runtime_site_packages = os.environ.get("VIDEO2ANIME_RUNTIME_SITEPACKAGES")
    if runtime_site_packages:
        runtime_base = Path(runtime_site_packages)
        dirs.extend(
            [
                runtime_base / "onnxruntime" / "capi",
                runtime_base / "nvidia" / "cudnn" / "bin",
                runtime_base / "nvidia" / "cublas" / "bin",
                runtime_base / "nvidia" / "cuda_runtime" / "bin",
            ]
        )

    cuda_path = os.environ.get("CUDA_PATH")
    if cuda_path:
        dirs.append(Path(cuda_path) / "bin")

    for base in site.getsitepackages() + [site.getusersitepackages()]:
        base_path = Path(base)
        dirs.extend(
            [
                base_path / "onnxruntime" / "capi",
                base_path / "nvidia" / "cudnn" / "bin",
                base_path / "nvidia" / "cublas" / "bin",
                base_path / "nvidia" / "cuda_runtime" / "bin",
                base_path / "torch" / "lib",
                base_path / "cv2",
            ]
        )

    seen = set()
    result: list[Path] = []
    for d in dirs:
        try:
            resolved = str(Path(d).resolve())
        except Exception:
            resolved = str(d)
        if resolved in seen:
            continue
        seen.add(resolved)
        if Path(d).exists():
            result.append(Path(d))
    return result


def _find_first_existing_dll(search_dirs: list[Path], name: str) -> Optional[Path]:
    for directory in search_dirs:
        candidate = directory / name
        if candidate.exists():
            return candidate
    return None


def _prepare_windows_gpu_runtime(log_fn: LogFn = None) -> list[Path]:
    if os.name != "nt":
        return []

    global _DLL_DIR_HANDLES
    log = log_fn or _default_log
    added = []
    for d in _candidate_windows_gpu_dirs():
        try:
            if hasattr(os, "add_dll_directory"):
                handle = os.add_dll_directory(str(d))
                _DLL_DIR_HANDLES.append(handle)
            added.append(str(d))
        except Exception:
            pass

    current_path = os.environ.get("PATH", "")
    prepend = [p for p in added if p not in current_path]
    if prepend:
        os.environ["PATH"] = os.pathsep.join(prepend + [current_path])
        log("Prepared GPU DLL search paths:\n- " + "\n- ".join(prepend))
    return [Path(p) for p in added]


def _preload_windows_gpu_runtime(log_fn: LogFn = None) -> None:
    if os.name != "nt":
        return

    global _DLL_PRELOAD_HANDLES
    log = log_fn or _default_log
    search_dirs = _candidate_windows_gpu_dirs()
    if not search_dirs:
        return

    preload_order = [
        # VC++ runtime next to the frozen app
        "VCRUNTIME140.dll",
        "VCRUNTIME140_1.dll",
        "MSVCP140.dll",
        "MSVCP140_1.dll",
        # ONNX Runtime core binaries
        "onnxruntime_providers_shared.dll",
        # CUDA runtime / math libs (best-effort; may be absent on CPU-only setups)
        "cudart64_110.dll",
        "cublas64_11.dll",
        "cublasLt64_11.dll",
        "cufft64_10.dll",
        "cudnn64_8.dll",
        "cudnn_ops_infer64_8.dll",
        "cudnn_cnn_infer64_8.dll",
        "cudnn_adv_infer64_8.dll",
        "cudnn_ops_train64_8.dll",
        "cudnn_cnn_train64_8.dll",
        "cudnn_adv_train64_8.dll",
        "onnxruntime_providers_cuda.dll",
    ]

    loaded_now = []
    for name in preload_order:
        dll_path = _find_first_existing_dll(search_dirs, name)
        if not dll_path:
            continue
        normalized = str(dll_path).lower()
        if normalized in _DLL_PRELOADED_PATHS:
            continue
        try:
            handle = ctypes.WinDLL(str(dll_path))
            _DLL_PRELOAD_HANDLES.append(handle)
            _DLL_PRELOADED_PATHS.add(normalized)
            loaded_now.append(str(dll_path))
        except OSError as exc:
            # Best-effort: CPU fallback should still work on systems without CUDA DLLs.
            log(f"Skipped preloading {dll_path.name}: {exc}")

    if loaded_now:
        log("Preloaded native runtime DLLs:\n- " + "\n- ".join(loaded_now))


_ORT = None
_DLL_DIR_HANDLES = []
_DLL_PRELOAD_HANDLES = []
_DLL_PRELOADED_PATHS = set()


def _get_ort(log_fn: LogFn = None):
    global _ORT
    if _ORT is None:
        ensure_runtime_on_sys_path(log_fn)
        _prepare_windows_gpu_runtime(log_fn)
        _preload_windows_gpu_runtime(log_fn)
        import onnxruntime as ort  # delayed import for packaged/runtime-managed Windows runtime
        _ORT = ort
    return _ORT


@dataclass
class VideoInfo:
    width: int
    height: int
    fps: float
    frame_count: int


class AnimeVideoConverter:
    def __init__(
        self,
        style: str = "hayao",
        device: str = "auto",
        models_dir: Union[str, Path] = "models",
        log_fn: LogFn = None,
    ) -> None:
        if style not in STYLE_MODELS:
            raise ValueError(f"Unknown style: {style}")
        if device not in {"auto", "cuda", "cpu"}:
            raise ValueError(f"Unknown device: {device}")

        self.style = style
        self.device = device
        self.models_dir = Path(models_dir)
        self.log = log_fn or _default_log

        self.models_dir.mkdir(parents=True, exist_ok=True)
        _prepare_windows_gpu_runtime(self.log)
        self.model_path = self._ensure_model()
        self.session, self.active_provider = self._create_session()

        input_meta = self.session.get_inputs()[0]
        self.input_name = input_meta.name
        self.input_layout = self._resolve_input_layout(input_meta.shape)
        self.model_height, self.model_width = self._resolve_model_size(input_meta.shape, self.input_layout)

        self.log(f"Model ready: {self.model_path.name}")
        self.log(f"ONNX Runtime provider: {self.active_provider}")
        self.log(f"Model input layout: {self.input_layout}")
        self.log(f"Model input size: {self.model_width}x{self.model_height}")

    def _ensure_model(self) -> Path:
        meta = STYLE_MODELS[self.style]
        model_path = self.models_dir / meta["filename"]
        if model_path.exists() and model_path.stat().st_size > 0:
            return model_path

        self.log(f"Downloading model: {meta['label']}")
        response = requests.get(meta["url"], stream=True, timeout=120)
        response.raise_for_status()
        total = int(response.headers.get("content-length", "0"))
        written = 0
        tmp_path = model_path.with_suffix(model_path.suffix + ".part")
        with tmp_path.open("wb") as fh:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                fh.write(chunk)
                written += len(chunk)
                if total:
                    pct = written / total * 100
                    self.log(f"Downloading model... {pct:.1f}%")
        tmp_path.replace(model_path)
        return model_path

    def _create_session(self):
        ort = _get_ort(self.log)
        sess_options = ort.SessionOptions()
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        available = ort.get_available_providers()

        if self.device == "cpu":
            if "CPUExecutionProvider" not in available:
                raise RuntimeError(f"CPUExecutionProvider is unavailable. available={available}")
            session = ort.InferenceSession(
                str(self.model_path),
                sess_options=sess_options,
                providers=["CPUExecutionProvider"],
            )
            return session, session.get_providers()[0]

        if self.device == "cuda":
            if "CUDAExecutionProvider" not in available:
                raise RuntimeError(f"CUDAExecutionProvider is unavailable. available={available}")
            session = ort.InferenceSession(
                str(self.model_path),
                sess_options=sess_options,
                providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
            )
            return session, session.get_providers()[0]

        if "CUDAExecutionProvider" in available:
            try:
                session = ort.InferenceSession(
                    str(self.model_path),
                    sess_options=sess_options,
                    providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
                )
                active = session.get_providers()[0]
                self.log(f"Auto device selected provider: {active}")
                return session, active
            except Exception as exc:
                self.log(f"CUDA provider failed to initialize; falling back to CPU. Reason: {exc}")

        if "CPUExecutionProvider" not in available:
            raise RuntimeError(
                "No usable ONNX Runtime providers are available. "
                f"available={available}"
            )

        session = ort.InferenceSession(
            str(self.model_path),
            sess_options=sess_options,
            providers=["CPUExecutionProvider"],
        )
        return session, session.get_providers()[0]

    @staticmethod
    def _resolve_input_layout(shape) -> str:
        if shape and len(shape) == 4:
            if shape[3] == 3:
                return "NHWC"
            if shape[1] == 3:
                return "NCHW"
        return "NHWC"

    @staticmethod
    def _resolve_model_size(shape, layout: str) -> tuple[int, int]:
        default_h, default_w = 512, 512
        if not shape or len(shape) != 4:
            return default_h, default_w

        if layout == "NHWC":
            h = shape[1]
            w = shape[2]
        else:
            h = shape[2]
            w = shape[3]

        if isinstance(h, int) and h > 0 and isinstance(w, int) and w > 0:
            return h, w
        return default_h, default_w

    @staticmethod
    def _letterbox(image: np.ndarray, target_w: int, target_h: int):
        src_h, src_w = image.shape[:2]
        scale = min(target_w / src_w, target_h / src_h)
        new_w = max(1, int(round(src_w * scale)))
        new_h = max(1, int(round(src_h * scale)))

        resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
        canvas = np.full((target_h, target_w, 3), 127, dtype=np.uint8)

        x0 = (target_w - new_w) // 2
        y0 = (target_h - new_h) // 2
        canvas[y0:y0 + new_h, x0:x0 + new_w] = resized
        return canvas, scale, x0, y0, new_w, new_h

    @staticmethod
    def _unletterbox(image: np.ndarray, src_w: int, src_h: int, x0: int, y0: int, new_w: int, new_h: int):
        cropped = image[y0:y0 + new_h, x0:x0 + new_w]
        return cv2.resize(cropped, (src_w, src_h), interpolation=cv2.INTER_CUBIC)

    def stylize_frame(self, frame_bgr: np.ndarray) -> np.ndarray:
        src_h, src_w = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        canvas, _scale, x0, y0, new_w, new_h = self._letterbox(rgb, self.model_width, self.model_height)

        x = canvas.astype(np.float32) / 127.5 - 1.0
        if self.input_layout == "NCHW":
            x = np.transpose(x, (2, 0, 1))[None, ...]
        else:
            x = x[None, ...]

        output = self.session.run(None, {self.input_name: x})[0]
        output = np.squeeze(output)

        if output.ndim == 3 and output.shape[0] in {1, 3} and output.shape[-1] not in {1, 3}:
            output = np.transpose(output, (1, 2, 0))

        output = np.clip((output + 1.0) * 127.5, 0, 255).astype(np.uint8)
        output = self._unletterbox(output, src_w, src_h, x0, y0, new_w, new_h)
        return cv2.cvtColor(output, cv2.COLOR_RGB2BGR)

    def inspect_video(self, input_path: Union[str, Path]) -> VideoInfo:
        cap = cv2.VideoCapture(str(input_path))
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open input video: {input_path}")
        try:
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        finally:
            cap.release()

        if fps <= 0:
            fps = 24.0
        return VideoInfo(width=width, height=height, fps=fps, frame_count=frame_count)

    def convert_video(
        self,
        input_path: Union[str, Path],
        output_path: Union[str, Path],
        progress_fn: ProgressFn = None,
        keep_audio: bool = True,
    ) -> dict:
        input_path = Path(input_path)
        output_path = Path(output_path)
        progress = progress_fn or (lambda _ratio, _msg: None)

        if not input_path.exists():
            raise FileNotFoundError(input_path)

        info = self.inspect_video(input_path)
        self.log(
            f"Input video: {info.width}x{info.height}, {info.fps:.3f} fps, {info.frame_count} frames"
        )
        progress(0.01, "Reading video metadata")

        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="video2anime_") as tmp_dir:
            tmp_dir_path = Path(tmp_dir)
            temp_video = tmp_dir_path / "stylized_video.mp4"
            temp_audio = tmp_dir_path / "audio.m4a"

            self._extract_audio(ffmpeg_exe, input_path, temp_audio, keep_audio)
            self._render_video_frames(input_path, temp_video, info, progress)
            self._finalize_output(ffmpeg_exe, temp_video, temp_audio, output_path)

        progress(1.0, "Done")
        self.log(f"Saved output: {output_path}")
        return {
            "input": str(input_path),
            "output": str(output_path),
            "provider": self.active_provider,
            "style": self.style,
            "video": {
                "width": info.width,
                "height": info.height,
                "fps": info.fps,
                "frame_count": info.frame_count,
            },
        }

    def _render_video_frames(
        self,
        input_path: Path,
        temp_video: Path,
        info: VideoInfo,
        progress: Callable[[float, str], None],
    ) -> None:
        cap = cv2.VideoCapture(str(input_path))
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open input video: {input_path}")

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(temp_video), fourcc, info.fps, (info.width, info.height))
        if not writer.isOpened():
            cap.release()
            raise RuntimeError("Cannot create output video writer")

        try:
            frame_index = 0
            total = max(info.frame_count, 1)
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                styled = self.stylize_frame(frame)
                writer.write(styled)
                frame_index += 1
                if frame_index == 1 or frame_index % 10 == 0 or frame_index == total:
                    ratio = min(0.98, frame_index / total)
                    progress(ratio, f"Processing frame {frame_index}/{total}")
        finally:
            cap.release()
            writer.release()

    def _extract_audio(self, ffmpeg_exe: str, input_path: Path, temp_audio: Path, keep_audio: bool) -> None:
        if not keep_audio:
            self.log("Audio retention disabled")
            return

        cmd = [
            ffmpeg_exe,
            "-y",
            "-i",
            str(input_path),
            "-vn",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            str(temp_audio),
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            self.log("No audio stream extracted (or audio extraction failed). Output will be video-only.")
        else:
            self.log("Audio extracted successfully")

    def _finalize_output(
        self,
        ffmpeg_exe: str,
        temp_video: Path,
        temp_audio: Path,
        output_path: Path,
    ) -> None:
        if temp_audio.exists() and temp_audio.stat().st_size > 0:
            cmd = [
                ffmpeg_exe,
                "-y",
                "-i",
                str(temp_video),
                "-i",
                str(temp_audio),
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-shortest",
                str(output_path),
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.returncode == 0:
                self.log("Merged original audio into output video")
                return
            self.log("Audio merge failed; falling back to video-only output")

        shutil.copy2(temp_video, output_path)


def export_run_metadata(target_path: Union[str, Path], payload: dict) -> None:
    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
