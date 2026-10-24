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
import subprocess
import sys
import threading
import time
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

MODELS = {
    "parakeet": (
        "parakeet-unified-en-0.6b-Q8_0.gguf",
        (
            "https://huggingface.co/handy-computer/"
            "parakeet-unified-en-0.6b-gguf/resolve/main/"
            "parakeet-unified-en-0.6b-Q8_0.gguf"
        ),
        "731 MB",
    ),
    "qwen": (
        "Qwen3-ASR-0.6B-Q8_0.gguf",
        (
            "https://huggingface.co/handy-computer/Qwen3-ASR-0.6B-gguf/"
            "resolve/main/Qwen3-ASR-0.6B-Q8_0.gguf"
        ),
        "850 MB",
    ),
}
SAMPLE_RATE = 16_000
BLOCK_SIZE = 512
INPUT_DEVICE: int | str | None = None
IGNORED_WINDOW_CLASSES = {"remmina"}

TOGGLE = "toggle"
CANCEL = "cancel"
logger = logging.getLogger(__name__)

_FINALIZE_STREAM = object()
_CANCEL_STREAM = object()


class StreamingTranscriber:
    """Feed microphone frames to transcribe.cpp away from the audio callback."""

    def __init__(self, model: transcribe_cpp.Model) -> None:
        self._model = model
        self._commands: queue.SimpleQueue[np.ndarray | object] = queue.SimpleQueue()
        self._cancelled = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            name="streaming-transcriber",
            daemon=True,
        )
        self._text = ""
        self._error: Exception | None = None

    def start(self) -> None:
        self._thread.start()

    def feed(self, samples: np.ndarray) -> None:
        # Handy routes frames through a channel so inference can never block
        # the real-time microphone callback. SimpleQueue is unbounded too.
        self._commands.put(samples)

    def finish(self) -> str:
        self._commands.put(_FINALIZE_STREAM)
        self._thread.join()
        if self._error is not None:
            raise self._error
        return self._text

    def cancel(self) -> None:
        # Match Handy's cancellation flag: queued frames are discarded instead
        # of being decoded before the cancel command reaches the worker.
        self._cancelled.set()
        self._commands.put(_CANCEL_STREAM)
        self._thread.join()

    def _run(self) -> None:
        try:
            with self._model.session() as session, session.stream() as stream:
                logger.info("Live streaming transcription started.")
                while True:
                    command = self._commands.get()
                    if command is _CANCEL_STREAM:
                        return
                    if command is _FINALIZE_STREAM:
                        stream.finalize()
                        self._text = stream.text().display.strip()
                        return
                    if self._cancelled.is_set():
                        continue
                    assert isinstance(command, np.ndarray)
                    stream.feed(command)
        except Exception as exc:
            self._error = exc


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
        action: str | None = None
        if key == keyboard.Key.esc:
            action = CANCEL
        elif key == keyboard.Key.space and pressed.intersection(ctrl_keys):
            action = TOGGLE
        if action is not None and not hotkeys_blocked():
            emit(action)

    def on_release(key: Any) -> None:
        pressed.discard(key)

    return on_press, on_release


def hotkeys_blocked() -> bool:
    """Return whether the focused X11 window has an ignored WM_CLASS."""
    if sys.platform != "linux" or not os.environ.get("DISPLAY"):
        return False

    try:
        from Xlib import X, display

        connection = display.Display()
        try:
            root = connection.screen().root
            active_window_atom = connection.intern_atom("_NET_ACTIVE_WINDOW")
            active_window = root.get_full_property(
                active_window_atom, X.AnyPropertyType
            )
            if active_window is None or not active_window.value:
                return False
            window = connection.create_resource_object(
                "window", int(active_window.value[0])
            )
            active_classes = {
                part.casefold()
                for value in window.get_wm_class() or ()
                for part in (value, *value.split("."))
            }
            ignored_classes = {value.casefold() for value in IGNORED_WINDOW_CLASSES}
            return not active_classes.isdisjoint(ignored_classes)
        finally:
            connection.close()
    except Exception:
        logger.debug("Could not identify the active X11 window", exc_info=True)
        return False


def cache_dir() -> Path:
    if sys.platform == "win32":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    elif sys.platform == "darwin":
        root = Path.home() / "Library/Caches"
    else:
        root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return root / "dictate"


def get_model() -> Path:
    key = os.environ.get("DICTATE_MODEL", "parakeet").casefold()
    try:
        filename, url, size = MODELS[key]
    except KeyError as exc:
        choices = ", ".join(MODELS)
        raise ValueError(
            f"Unknown DICTATE_MODEL={key!r}; choose one of: {choices}"
        ) from exc
    path = cache_dir() / filename
    if path.is_file():
        return path

    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix + ".part")
    logger.info("Downloading %s (about %s)...", filename, size)
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "dictate/0.1"})
        with urllib.request.urlopen(request) as response, partial.open("wb") as output:
            shutil.copyfileobj(response, output)
        partial.replace(path)
    except Exception:
        partial.unlink(missing_ok=True)
        raise
    return path


def record(
    model: transcribe_cpp.Model,
    events: queue.Queue[str],
    status: StatusSignals,
) -> np.ndarray | str | None:
    streaming = model.capabilities.supports_streaming
    chunks: list[np.ndarray] | None = None if streaming else []
    streamer = StreamingTranscriber(model) if streaming else None
    if streamer is not None:
        streamer.start()
    else:
        logger.info("Model does not support streaming; using batch transcription.")

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
        if streamer is not None:
            streamer.feed(samples)
        else:
            assert chunks is not None
            chunks.append(samples)
        rms = float(np.sqrt(np.mean(np.square(samples), dtype=np.float64)))
        # A logarithmic dBFS meter tracks perceived loudness more naturally
        # than displaying the raw linear waveform amplitude.
        dbfs = 20 * math.log10(max(rms, 1e-9))
        status.level.emit(max(0.0, min(1.0, (dbfs + 60.0) / 48.0)))

    try:
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
    except BaseException:
        if streamer is not None:
            streamer.cancel()
        raise

    if action == CANCEL:
        if streamer is not None:
            streamer.cancel()
        logger.info("Cancelled.")
        status.changed.emit("idle")
        return None
    if chunks is not None and not chunks:
        logger.info("No audio recorded.")
        status.changed.emit("idle")
        return None
    status.changed.emit("transcribing")
    if streamer is None:
        assert chunks is not None
        return np.concatenate(chunks)

    stopped_at = time.perf_counter()
    text = streamer.finish()
    logger.info(
        "Stream finalized in %.0f ms.",
        (time.perf_counter() - stopped_at) * 1000,
    )
    return text


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

        result = record(model, events, status)
        if result is None:
            continue

        text = result if isinstance(result, str) else transcribe(model, result)
        if text:
            # Use delayed xdotool input to prevent incorrect X11 Unicode characters.
            if sys.platform == "linux" and not text.isascii():
                subprocess.run(
                    [
                        "xdotool",
                        "type",
                        "--clearmodifiers",
                        "--file",
                        "-",
                    ],
                    input=text,
                    text=True,
                    check=True,
                )
            else:
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
