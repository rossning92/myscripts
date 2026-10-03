# Dictate

Local speech-to-text using Parakeet Unified EN 0.6B through `transcribe.cpp`.

```bash
cd scripts/r/dictate
uv sync
uv run dictate.py
```

- `Ctrl+Space`: start or stop recording
- `Escape`: cancel the active recording
- `Ctrl+C`: quit

A small click-through status pill appears at the bottom center, showing animated
audio bars while listening and pulsing dots while transcribing. It stays hidden
while idle and never takes focus from your current application.

The first run downloads the same quantized Q8 GGUF used by Handy (about 700 MB)
to the operating system's user cache. NeMo and PyTorch are not used.

Linux needs PortAudio and an X11 session; macOS needs Accessibility and
Microphone permissions. Windows may also request Microphone permission.
