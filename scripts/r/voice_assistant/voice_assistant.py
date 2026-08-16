#!/usr/bin/env python3
"""Listen for a wake word, then print the following speech as text.

Run with ``uv run voice_assistant.py``. The first run downloads the
selected openWakeWord and Whisper models.
"""

from __future__ import annotations

import queue
import re
import sys
from collections import deque
from pathlib import Path

import numpy as np
import openwakeword
import sounddevice as sd
from faster_whisper import WhisperModel
from openwakeword.model import Model as WakeModel

# Configuration
WAKE_MODEL = "hey_rhasspy"  # Bundled model name or path to a custom .onnx model
WAKE_PHRASE = "hey rhasspy"  # Removed if Whisper includes it in the transcript
WAKE_THRESHOLD = 0.5

WHISPER_MODEL = "base.en"
LANGUAGE: str | None = "en"  # Use None for automatic language detection
DEVICE = "cpu"  # "cpu" or "cuda"
COMPUTE_TYPE: str | None = None  # Defaults to int8 on CPU and float16 on CUDA
BEAM_SIZE = 5

INPUT_DEVICE: int | str | None = None  # Device index, name, or None for default
SAMPLE_RATE = 16_000
CHUNK_SAMPLES = 1_280  # openWakeWord's native 80 ms frame size
SILENCE_SECONDS = 0.9
START_TIMEOUT_SECONDS = 3.0
MAX_COMMAND_SECONDS = 30.0
MIN_RMS = 250.0
NOISE_MULTIPLIER = 2.5
NOISE_HISTORY_CHUNKS = 100


def rms(chunk: np.ndarray) -> float:
    samples = chunk.astype(np.float32)
    return float(np.sqrt(np.mean(samples * samples)))


def strip_wake_phrase(text: str, phrase: str) -> str:
    text = text.strip()
    words = [re.escape(word) for word in phrase.split()]
    if not words:
        return text
    prefix = r"^\s*" + r"[\s,;:!?.-]+".join(words) + r"[\s,;:!?.-]*"
    return re.sub(prefix, "", text, count=1, flags=re.IGNORECASE).strip()


def ensure_wake_model(openwakeword, model: str) -> None:
    if Path(model).exists():
        return
    try:
        openwakeword.utils.download_models([model])
    except Exception as exc:
        raise SystemExit(
            f"Could not download openWakeWord model {model!r}. "
            f"Use a valid bundled model name or a model file path.\n{exc}"
        ) from exc


def main() -> int:
    ensure_wake_model(openwakeword, WAKE_MODEL)
    try:
        wake_model = WakeModel(
            wakeword_models=[WAKE_MODEL],
            inference_framework="onnx",
        )
    except Exception as exc:
        raise SystemExit(f"Could not load wake-word model: {exc}") from exc

    compute_type = COMPUTE_TYPE or ("int8" if DEVICE == "cpu" else "float16")
    print(f"Loading Whisper model {WHISPER_MODEL!r}...", file=sys.stderr)
    whisper = WhisperModel(
        WHISPER_MODEL,
        device=DEVICE,
        compute_type=compute_type,
    )

    audio_queue: queue.Queue[np.ndarray] = queue.Queue()

    def audio_callback(indata, frames, callback_time, status) -> None:
        del frames, callback_time
        if status:
            print(f"Audio warning: {status}", file=sys.stderr)
        audio_queue.put(indata[:, 0].copy())

    silence_chunks = max(1, round(SILENCE_SECONDS * SAMPLE_RATE / CHUNK_SAMPLES))
    max_chunks = max(1, round(MAX_COMMAND_SECONDS * SAMPLE_RATE / CHUNK_SAMPLES))
    start_timeout_chunks = max(
        1, round(START_TIMEOUT_SECONDS * SAMPLE_RATE / CHUNK_SAMPLES)
    )
    noise_levels: deque[float] = deque(maxlen=NOISE_HISTORY_CHUNKS)

    print(
        f"Listening for {WAKE_MODEL!r}; press Ctrl-C to stop.",
        file=sys.stderr,
    )
    try:
        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            blocksize=CHUNK_SAMPLES,
            channels=1,
            dtype="int16",
            device=INPUT_DEVICE,
            callback=audio_callback,
        ):
            while True:
                chunk = audio_queue.get()
                level = rms(chunk)
                noise_levels.append(level)
                predictions = wake_model.predict(chunk)
                score = max(float(value) for value in predictions.values())
                if score < WAKE_THRESHOLD:
                    continue

                noise_floor = float(np.median(noise_levels)) if noise_levels else 0.0
                speech_threshold = max(MIN_RMS, noise_floor * NOISE_MULTIPLIER)
                print(
                    f"Wake word detected ({score:.2f}); listening...",
                    file=sys.stderr,
                )

                command_chunks: list[np.ndarray] = []
                quiet_chunks = 0
                speech_started = False
                for index in range(max_chunks):
                    command_chunk = audio_queue.get()
                    command_chunks.append(command_chunk)
                    if rms(command_chunk) >= speech_threshold:
                        speech_started = True
                        quiet_chunks = 0
                    elif speech_started:
                        quiet_chunks += 1

                    if speech_started and quiet_chunks >= silence_chunks:
                        break
                    if not speech_started and index >= start_timeout_chunks:
                        break

                wake_model.reset()
                if not speech_started:
                    print("No command heard.", file=sys.stderr)
                    continue

                # Remove endpoint silence, convert PCM16 to the float32 format Whisper accepts.
                if quiet_chunks:
                    command_chunks = command_chunks[:-quiet_chunks]
                audio = np.concatenate(command_chunks).astype(np.float32) / 32768.0
                print("Transcribing...", file=sys.stderr)
                segments, _ = whisper.transcribe(
                    audio,
                    language=LANGUAGE,
                    beam_size=BEAM_SIZE,
                    vad_filter=True,
                    condition_on_previous_text=False,
                )
                transcript = " ".join(
                    segment.text.strip() for segment in segments
                ).strip()
                transcript = strip_wake_phrase(transcript, WAKE_PHRASE)
                if transcript:
                    print(transcript, flush=True)
                else:
                    print("No speech recognized.", file=sys.stderr)
    except KeyboardInterrupt:
        print("\nStopped.", file=sys.stderr)
        return 0
    except Exception as exc:
        raise SystemExit(f"Audio input failed: {exc}") from exc


if __name__ == "__main__":
    raise SystemExit(main())
