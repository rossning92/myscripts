#!/usr/bin/env python3
"""Generate a video from an image with OpenRouter's asynchronous video API."""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from utils.getch import getch
from utils.shutil import shell_open


_BASE_URL = "https://openrouter.ai/api/v1/"
_POLL_INTERVAL = 5.0
_END_STATUSES = {"completed", "failed", "cancelled", "expired"}


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be true or false")


def _env_number(
    name: str, default: int | float | None, convert: type[int] | type[float]
):
    value = os.environ.get(name)
    if value in (None, ""):
        return default
    try:
        return convert(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a valid {convert.__name__}") from exc


def _image_file_from_env(name: str, required: bool = False) -> Path | None:
    value = os.environ.get(name)
    if not value:
        if required:
            raise ValueError(f"{name} is required")
        return None

    path = Path(value).expanduser()
    if not path.is_file():
        raise ValueError(f"{name} is not a readable file: {path}")
    mime_type, _ = mimetypes.guess_type(path.name)
    if not mime_type or not mime_type.startswith("image/"):
        raise ValueError(f"{name} must identify a recognized image file: {path}")
    return path


def _image_data_url(path: Path) -> str:
    mime_type, _ = mimetypes.guess_type(path.name)
    if not mime_type or not mime_type.startswith("image/"):
        raise ValueError(f"Could not determine the image MIME type: {path}")
    try:
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    except OSError as exc:
        raise ValueError(f"Could not read image file {path}: {exc}") from exc
    return f"data:{mime_type};base64,{encoded}"


def _model_capabilities(
    session: requests.Session, api_root: str, model: str
) -> dict[str, Any]:
    response = _request_json(session, "GET", urljoin(api_root, "videos/models"))
    for candidate in response.get("data", []):
        if candidate.get("id") == model or candidate.get("canonical_slug") == model:
            return candidate
    raise ValueError(f"OpenRouter's video models endpoint does not list {model}")


def _request_json(
    session: requests.Session, method: str, url: str, **kwargs: Any
) -> dict[str, Any]:
    try:
        response = session.request(method, url, timeout=60, **kwargs)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        detail = getattr(exc.response, "text", "")
        message = f"OpenRouter request failed: {exc}\n{detail}".rstrip()
        raise RuntimeError(message) from exc
    except requests.JSONDecodeError as exc:
        raise RuntimeError("OpenRouter returned an invalid JSON response") from exc


def _download_video(
    session: requests.Session, url: str, output: Path, api_root: str
) -> None:
    download_url = (
        url if url.startswith(("https://", "http://")) else urljoin(api_root, url)
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with session.get(download_url, stream=True, timeout=300) as response:
            response.raise_for_status()
            with output.open("wb") as file:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        file.write(chunk)
    except requests.RequestException as exc:
        raise RuntimeError(f"Video download failed: {exc}") from exc


def _main() -> int:
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    image_file = _image_file_from_env("I2V_IMAGE_FILE", required=True)
    assert image_file is not None
    last_frame_file = _image_file_from_env("I2V_LAST_FRAME_FILE")
    prompt = os.environ.get("I2V_PROMPT", "")
    if not prompt:
        raise ValueError("I2V_PROMPT is required")

    duration = _env_number("I2V_DURATION", 5, int)
    if duration <= 0:
        raise ValueError("I2V_DURATION must be greater than zero")

    output_value = os.environ.get("I2V_OUTPUT")
    output = (
        Path(output_value).expanduser()
        if output_value
        else Path.home()
        / "Downloads"
        / f"i2v_{datetime.now():%Y%m%d_%H%M%S}.mp4"
    )
    api_root = _BASE_URL
    model = os.environ.get("I2V_MODEL", "alibaba/wan-2.7")

    session = requests.Session()
    if api_key:
        session.headers.update({"Authorization": f"Bearer {api_key}"})
    session.headers.update({"Content-Type": "application/json"})
    capabilities = _model_capabilities(session, api_root, model)

    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "duration": duration,
        "generate_audio": _env_bool("I2V_GENERATE_AUDIO", True),
    }
    seed = _env_number("I2V_SEED", None, int)
    if seed is not None:
        payload["seed"] = seed
    resolution = os.environ.get("I2V_RESOLUTION", "720p")
    supported_resolutions = capabilities.get("supported_resolutions") or []
    if supported_resolutions and resolution not in supported_resolutions:
        raise ValueError(
            f"{model} does not support I2V_RESOLUTION={resolution}; "
            "supported resolutions: " + ", ".join(supported_resolutions)
        )
    payload["resolution"] = resolution

    frames = [
        {
            "type": "image_url",
            "image_url": {"url": _image_data_url(image_file)},
            "frame_type": "first_frame",
        }
    ]
    if last_frame_file:
        frames.append(
            {
                "type": "image_url",
                "image_url": {"url": _image_data_url(last_frame_file)},
                "frame_type": "last_frame",
            }
        )
    payload["frame_images"] = frames

    if _env_bool("I2V_DRY_RUN", False):
        print(json.dumps(payload, indent=2))
        return 0

    if not api_key:
        raise ValueError("OPENROUTER_API_KEY is required unless I2V_DRY_RUN=true")

    job = _request_json(session, "POST", urljoin(api_root, "videos"), json=payload)
    job_id = job.get("id")
    if not job_id:
        raise RuntimeError(f"Submission response has no job ID: {job}")
    polling_url = job.get("polling_url") or urljoin(api_root, f"videos/{job_id}")
    print(f"Submitted job {job_id}", flush=True)

    last_status: str | None = None
    while True:
        job = _request_json(session, "GET", polling_url)
        status = str(job.get("status", "unknown"))
        if status != last_status:
            print(f"Status: {status}", flush=True)
            last_status = status
        if status in _END_STATUSES:
            break
        time.sleep(_POLL_INTERVAL)

    if status != "completed":
        error = job.get("error", "no error details")
        raise RuntimeError(f"Generation {status}: {error}")

    urls = job.get("unsigned_urls") or []
    content_url = urls[0] if urls else urljoin(
        api_root, f"videos/{job_id}/content?index=0"
    )
    _download_video(session, content_url, output, api_root)
    print(f"Saved video to {output.resolve()}")
    if job.get("usage"):
        print("Usage: " + json.dumps(job["usage"]))

    print("\033[2mo open  q quit\033[0m", end="", flush=True)
    while True:
        key = (getch() or "").lower()
        if key in {"o", "q", ""}:
            break
    print()
    if key == "o":
        shell_open(str(output.resolve()))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(_main())
    except (RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
