#!/usr/bin/env python3
"""Type locally transcribed speech into the focused application.

Run with ``uv run dictate.py``. Ctrl+Space starts/stops recording; Escape
cancels the current recording.
"""

from __future__ import annotations

import logging
import math
import os
import queue
import signal
import shutil
import sys
import threading
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import sounddevice as sd
import transcribe_cpp
from pynput import keyboard
from PySide6 import QtCore, QtWidgets

from overlay import StatusOverlay, StatusSignals

MODEL_NAME = "parakeet-unified-en-0.6b-Q8_0.gguf"
MODEL_URL = (
    "https://huggingface.co/handy-computer/parakeet-unified-en-0.6b-gguf/"
    f"resolve/main/{MODEL_NAME}"
)
SAMPLE_RATE = 16_000
BLOCK_SIZE = 512
INPUT_DEVICE: int | str | None = None

TOGGLE = "toggle"
CANCEL = "cancel"
logger = logging.getLogger(__name__)


def make_hotkey_callbacks(
    emit: Callable[[str], None],
) -> tuple[Callable[[Any], None], Callable[[Any], None]]:
    """Build callbacks with one event per physical Ctrl+Space press."""
    pressed: set[Any] = set()
    ctrl_keys = {keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r}

    def on_press(key: Any) -> None:
        if key in pressed:
            return
        pressed.add(key)
        if key == keyboard.Key.esc:
            emit(CANCEL)
        elif key == keyboard.Key.space and pressed.intersection(ctrl_keys):
            emit(TOGGLE)

    def on_release(key: Any) -> None:
        pressed.discard(key)

    return on_press, on_release


def cache_dir() -> Path:
    if sys.platform == "win32":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    elif sys.platform == "darwin":
        root = Path.home() / "Library/Caches"
    else:
        root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return root / "dictate"


def get_model() -> Path:
    path = cache_dir() / MODEL_NAME
    if path.is_file():
        return path

    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix + ".part")
    logger.info("Downloading %s (about 700 MB)...", MODEL_NAME)
    try:
        request = urllib.request.Request(MODEL_URL, headers={"User-Agent": "dictate/0.1"})
        with urllib.request.urlopen(request) as response, partial.open("wb") as output:
            shutil.copyfileobj(response, output)
        partial.replace(path)
    except Exception:
        partial.unlink(missing_ok=True)
        raise
    return path


def record(events: queue.Queue[str], status: StatusSignals) -> np.ndarray | None:
    chunks: list[np.ndarray] = []

    def audio_callback(
        indata: np.ndarray,
        frames: int,
        callback_time: Any,
        callback_status: sd.CallbackFlags,
    ) -> None:
        del frames, callback_time
        if callback_status:
            logger.warning("Audio: %s", callback_status)
        samples = indata[:, 0].copy()
        chunks.append(samples)
        rms = float(np.sqrt(np.mean(np.square(samples), dtype=np.float64)))
        # A logarithmic dBFS meter tracks perceived loudness more naturally
        # than displaying the raw linear waveform amplitude.
        dbfs = 20 * math.log10(max(rms, 1e-9))
        status.level.emit(max(0.0, min(1.0, (dbfs + 60.0) / 48.0)))

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        blocksize=BLOCK_SIZE,
        channels=1,
        dtype="float32",
        device=INPUT_DEVICE,
        callback=audio_callback,
    ):
        logger.info("Recording...")
        status.changed.emit("listening")
        action = events.get()

    if action == CANCEL:
        logger.info("Cancelled.")
        status.changed.emit("idle")
        return None
    if not chunks:
        logger.info("No audio recorded.")
        status.changed.emit("idle")
        return None
    status.changed.emit("transcribing")
    return np.concatenate(chunks)


def transcribe(model: transcribe_cpp.Model, audio: np.ndarray) -> str:
    logger.info("Transcribing...")
    with model.session() as session:
        return session.run(audio).text.strip()


def drain_events(events: queue.Queue[str]) -> None:
    while True:
        try:
            events.get_nowait()
        except queue.Empty:
            return


def dictate_loop(
    model: transcribe_cpp.Model,
    events: queue.Queue[str],
    status: StatusSignals,
) -> None:
    typer = keyboard.Controller()
    while True:
        if events.get() != TOGGLE:
            continue

        audio = record(events, status)
        if audio is None:
            continue

        text = transcribe(model, audio)
        if text:
            typer.type(text)
            logger.info("Transcribed: %s", text)
        else:
            logger.info("No speech recognized.")
        status.changed.emit("idle")
        drain_events(events)


def run_dictation(events: queue.Queue[str], status: StatusSignals) -> None:
    """Load the model and run dictation away from Qt's UI thread."""
    on_press, on_release = make_hotkey_callbacks(events.put)
    try:
        model_path = get_model()
        with (
            transcribe_cpp.Model(str(model_path)) as model,
            keyboard.Listener(on_press=on_press, on_release=on_release),
        ):
            logger.info("Ready. Ctrl+Space: start/stop; Escape: cancel.")
            dictate_loop(model, events, status)
    except Exception as exc:
        logger.exception("Dictation failed")
        status.failed.emit(str(exc))


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("Dictate")
    app.setQuitOnLastWindowClosed(False)

    lock_path = cache_dir() / "instance.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    instance_lock = QtCore.QLockFile(str(lock_path))
    if not instance_lock.tryLock(0):
        logger.info("Dictate is already running.")
        return 0

    events: queue.Queue[str] = queue.Queue()
    status = StatusSignals()
    overlay = StatusOverlay()
    status.changed.connect(overlay.set_status)
    status.level.connect(overlay.set_audio_level)

    exit_code = 0

    @QtCore.Slot(str)
    def show_error(message: str) -> None:
        nonlocal exit_code
        exit_code = 1
        logger.error("Dictation failed: %s", message)
        overlay.set_status("error")
        QtCore.QTimer.singleShot(3000, app.quit)

    status.failed.connect(show_error)
    worker = threading.Thread(
        target=run_dictation,
        args=(events, status),
        name="dictation-worker",
        daemon=True,
    )
    worker.start()

    signal.signal(signal.SIGINT, lambda *_: app.quit())
    signal.signal(signal.SIGTERM, lambda *_: app.quit())
    keep_signals_alive = QtCore.QTimer()
    keep_signals_alive.start(250)
    keep_signals_alive.timeout.connect(lambda: None)

    app.exec()
    logger.info("Stopped.")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
