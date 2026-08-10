import argparse
import logging
import os

import requests

DEFAULT_PROMPT = "audio is english and simplified chinese."


def convert_audio_to_text(file: str, prompt: str = DEFAULT_PROMPT) -> str:
    logging.info(f"Converting audio to text: {file}")

    # https://platform.openai.com/docs/guides/speech-to-text
    url = "https://api.openai.com/v1/audio/transcriptions"
    headers = {"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"]}
    payload = {
        "model": "gpt-4o-mini-transcribe",
        "prompt": prompt,
    }
    with open(file, "rb") as f:
        files = {
            "file": (
                os.path.basename(file),
                f,
                "application/octet-stream",
            )
        }
        response = requests.post(url, headers=headers, data=payload, files=files)
    json = response.json()
    if "text" not in json:
        raise ValueError(f"Invalid result: {json}")
    return json["text"]


def _main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=str, help="Path to the audio file", required=True)
    args = parser.parse_args()

    result = convert_audio_to_text(args.file)
    print(result, end="")


if __name__ == "__main__":
    _main()
