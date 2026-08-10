import os
import shutil
import subprocess
from pathlib import Path

_DEFAULT_MODEL = Path(
    os.environ.get(
        "WHISPER_CPP_MODEL",
        "~/.local/share/whisper-cpp/ggml-tiny.en.bin",
    )
).expanduser()


def convert_audio_to_text(file: str) -> str:
    whisper_cli = shutil.which("whisper-cli")
    if whisper_cli is None:
        raise RuntimeError(
            "whisper-cli is not installed; install it with: sudo pacman -S whisper-cpp"
        )

    model = _DEFAULT_MODEL
    if not model.is_file():
        raise FileNotFoundError(
            f"Whisper model not found: {model}\n"
            "Download ggml-tiny.en.bin or set WHISPER_CPP_MODEL."
        )

    result = subprocess.run(
        [
            whisper_cli,
            "--model",
            str(model),
            "--file",
            file,
            "--language",
            "en",
            "--no-timestamps",
            "--no-prints",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()
