from __future__ import annotations

import argparse
import os
import queue
import sys
import threading
import traceback
from pathlib import Path
from typing import Optional, Union
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from anime_pipeline import AnimeVideoConverter, STYLE_MODELS, export_run_metadata


APP_TITLE = "Video to Anime (CUDA / Windows)"
DEFAULT_OUTPUT_SUFFIX = "_anime.mp4"


def get_models_dir() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Video2AnimeCUDA"
        base.mkdir(parents=True, exist_ok=True)
        return base / "models"
    return Path(__file__).resolve().parent / "models"


class AnimeApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("860x620")

        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.worker: Optional[threading.Thread] = None

        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.style_var = tk.StringVar(value="hayao")
        self.device_var = tk.StringVar(value="auto")
        self.keep_audio_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="Ready")
        self.progress_var = tk.DoubleVar(value=0.0)

        self._build_ui()
        self.root.after(120, self._drain_events)

    def _build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=16)
        main.pack(fill="both", expand=True)

        title = ttk.Label(main, text=APP_TITLE, font=("Segoe UI", 16, "bold"))
        title.pack(anchor="w")

        desc = ttk.Label(
            main,
            text=(
                "本地视频动画化工具。默认使用 AnimeGANv2，优先尝试 CUDA，"
                "会自动下载模型并尽量保留原音频。"
            ),
            wraplength=760,
        )
        desc.pack(anchor="w", pady=(6, 14))

        form = ttk.Frame(main)
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="Input video").grid(row=0, column=0, sticky="w", pady=6)
        ttk.Entry(form, textvariable=self.input_var).grid(row=0, column=1, sticky="ew", padx=8, pady=6)
        ttk.Button(form, text="Browse...", command=self.choose_input).grid(row=0, column=2, sticky="ew", pady=6)

        ttk.Label(form, text="Output video").grid(row=1, column=0, sticky="w", pady=6)
        ttk.Entry(form, textvariable=self.output_var).grid(row=1, column=1, sticky="ew", padx=8, pady=6)
        ttk.Button(form, text="Save as...", command=self.choose_output).grid(row=1, column=2, sticky="ew", pady=6)

        ttk.Label(form, text="Style").grid(row=2, column=0, sticky="w", pady=6)
        style_box = ttk.Combobox(
            form,
            textvariable=self.style_var,
            values=list(STYLE_MODELS.keys()),
            state="readonly",
        )
        style_box.grid(row=2, column=1, sticky="w", padx=8, pady=6)

        ttk.Label(form, text="Device").grid(row=3, column=0, sticky="w", pady=6)
        device_box = ttk.Combobox(
            form,
            textvariable=self.device_var,
            values=["auto", "cuda", "cpu"],
            state="readonly",
        )
        device_box.grid(row=3, column=1, sticky="w", padx=8, pady=6)

        ttk.Checkbutton(form, text="Keep original audio", variable=self.keep_audio_var).grid(
            row=4, column=1, sticky="w", padx=8, pady=6
        )

        actions = ttk.Frame(main)
        actions.pack(fill="x", pady=(14, 10))
        ttk.Button(actions, text="Start Convert", command=self.start_convert).pack(side="left")
        ttk.Button(actions, text="Open Output Folder", command=self.open_output_folder).pack(side="left", padx=8)

        ttk.Progressbar(main, variable=self.progress_var, maximum=100).pack(fill="x", pady=(4, 8))
        ttk.Label(main, textvariable=self.status_var).pack(anchor="w")

        log_frame = ttk.LabelFrame(main, text="Log", padding=8)
        log_frame.pack(fill="both", expand=True, pady=(14, 0))
        self.log_text = tk.Text(log_frame, height=20, wrap="word")
        self.log_text.pack(fill="both", expand=True)
        self.log_text.configure(state="disabled")

    def choose_input(self) -> None:
        path = filedialog.askopenfilename(
            title="Choose input video",
            filetypes=[("Video Files", "*.mp4 *.mov *.avi *.mkv *.wmv"), ("All Files", "*.*")],
        )
        if not path:
            return
        self.input_var.set(path)
        if not self.output_var.get().strip():
            out = self._default_output_path(path)
            self.output_var.set(str(out))

    def choose_output(self) -> None:
        initial = self.output_var.get().strip() or str(self._default_output_path(self.input_var.get().strip() or "output.mp4"))
        path = filedialog.asksaveasfilename(
            title="Choose output video",
            initialfile=Path(initial).name,
            defaultextension=".mp4",
            filetypes=[("MP4 Video", "*.mp4"), ("All Files", "*.*")],
        )
        if path:
            self.output_var.set(path)

    def _default_output_path(self, input_path: Union[str, Path]) -> Path:
        p = Path(input_path)
        if p.suffix:
            return p.with_name(p.stem + DEFAULT_OUTPUT_SUFFIX)
        return Path.cwd() / (p.name + DEFAULT_OUTPUT_SUFFIX)

    def open_output_folder(self) -> None:
        output = self.output_var.get().strip()
        if not output:
            messagebox.showinfo(APP_TITLE, "还没有输出路径。")
            return
        folder = Path(output).resolve().parent
        try:
            import os
            os.startfile(str(folder))  # type: ignore[attr-defined]
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"无法打开目录：{exc}")

    def start_convert(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo(APP_TITLE, "任务正在运行中。")
            return

        input_path = self.input_var.get().strip()
        output_path = self.output_var.get().strip()
        if not input_path:
            messagebox.showwarning(APP_TITLE, "请选择输入视频。")
            return
        if not output_path:
            output_path = str(self._default_output_path(input_path))
            self.output_var.set(output_path)

        self.progress_var.set(0)
        self.status_var.set("Starting...")
        self._append_log("=" * 60)
        self._append_log(f"Input : {input_path}")
        self._append_log(f"Output: {output_path}")
        self._append_log(f"Style : {self.style_var.get()}")
        self._append_log(f"Device: {self.device_var.get()}")

        self.worker = threading.Thread(
            target=self._worker_convert,
            args=(input_path, output_path, self.style_var.get(), self.device_var.get(), self.keep_audio_var.get()),
            daemon=True,
        )
        self.worker.start()

    def _worker_convert(self, input_path: str, output_path: str, style: str, device: str, keep_audio: bool) -> None:
        try:
            converter = AnimeVideoConverter(
                style=style,
                device=device,
                models_dir=get_models_dir(),
                log_fn=lambda msg: self.events.put(("log", msg)),
            )
            result = converter.convert_video(
                input_path,
                output_path,
                progress_fn=lambda ratio, msg: self.events.put(("progress", (ratio, msg))),
                keep_audio=keep_audio,
            )
            export_run_metadata(Path(output_path).with_suffix(".json"), result)
            self.events.put(("done", result))
        except Exception as exc:
            tb = traceback.format_exc()
            self.events.put(("error", f"{exc}\n\n{tb}"))

    def _drain_events(self) -> None:
        while True:
            try:
                kind, payload = self.events.get_nowait()
            except queue.Empty:
                break

            if kind == "log":
                self._append_log(str(payload))
            elif kind == "progress":
                ratio, msg = payload
                self.progress_var.set(max(0.0, min(100.0, float(ratio) * 100.0)))
                self.status_var.set(str(msg))
            elif kind == "done":
                self.progress_var.set(100.0)
                self.status_var.set("Done")
                output = payload.get("output") if isinstance(payload, dict) else None
                self._append_log("Finished successfully.")
                if output:
                    self._append_log(f"Saved to: {output}")
                messagebox.showinfo(APP_TITLE, "转换完成。")
            elif kind == "error":
                self.status_var.set("Failed")
                self._append_log(str(payload))
                messagebox.showerror(APP_TITLE, str(payload))

        self.root.after(120, self._drain_events)

    def _append_log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message.rstrip() + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=APP_TITLE)
    parser.add_argument("--input", help="Input video path")
    parser.add_argument("--output", help="Output video path")
    parser.add_argument("--style", choices=list(STYLE_MODELS.keys()), default="hayao")
    parser.add_argument("--device", choices=["auto", "cuda", "cpu"], default="auto")
    parser.add_argument("--no-audio", action="store_true", help="Do not keep original audio")
    return parser


def run_cli(args: argparse.Namespace) -> int:
    if not args.input:
        raise SystemExit("--input is required in CLI mode")

    input_path = Path(args.input)
    output_path = Path(args.output) if args.output else input_path.with_name(input_path.stem + DEFAULT_OUTPUT_SUFFIX)

    print(f"Input : {input_path}")
    print(f"Output: {output_path}")
    print(f"Style : {args.style}")
    print(f"Device: {args.device}")

    converter = AnimeVideoConverter(
        style=args.style,
        device=args.device,
        models_dir=get_models_dir(),
        log_fn=lambda msg: print(msg, flush=True),
    )
    result = converter.convert_video(
        input_path,
        output_path,
        progress_fn=lambda ratio, msg: print(f"[{ratio * 100:6.2f}%] {msg}", flush=True),
        keep_audio=not args.no_audio,
    )
    export_run_metadata(output_path.with_suffix(".json"), result)
    print("Done")
    return 0


def run_gui() -> None:
    root = tk.Tk()
    root.mainloop = root.mainloop  # keep linters quiet on some setups
    AnimeApp(root)
    root.mainloop()


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()

    if args.input:
        raise SystemExit(run_cli(args))
    run_gui()
