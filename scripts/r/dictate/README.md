# Dictate

Local speech-to-text using `transcribe.cpp`.

Streaming-capable models are transcribed while recording, minimizing the wait
after the shortcut is released. Audio frames pass through a worker queue so
inference never blocks microphone capture. Batch transcription is used only
for models that do not support streaming.

```bash
cd scripts/r/dictate
uv sync
uv run dictate.py
```

- `Ctrl+Space`: start or stop recording
- `Escape`: cancel the active recording
- `Ctrl+C`: quit

Select a model with `DICTATE_MODEL`. Parakeet remains the default:

```bash
DICTATE_MODEL=parakeet uv run dictate.py  # English; default
DICTATE_MODEL=qwen uv run dictate.py      # Chinese + English
```

Hotkeys are disabled while a window whose class appears in
`IGNORED_WINDOW_CLASSES` is focused. The default list contains Remmina so its
keyboard grab sends the keys only to the remote machine.

A small click-through status pill appears at the bottom center, showing animated
audio bars while listening and pulsing dots while transcribing. It stays hidden
while idle and never takes focus from your current application.

The first use of a model downloads its quantized Q8 GGUF published by Handy to
the operating system's user cache. NeMo and PyTorch are not used.

Linux needs PortAudio, `xdotool`, and an X11 session; macOS needs Accessibility
and Microphone permissions. Windows may also request Microphone permission.
