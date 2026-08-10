import argparse
import os
import tempfile
from threading import Event, Thread
from typing import Callable, Optional

import ai.openai.speech_to_text
import ai.whisper.speech_to_text
from audio.record_audio import record_audio
from utils.getch import getch


def _record_and_convert(convert: Callable[[str], str]) -> Optional[str]:
    fd, out_file = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    stop_event = Event()
    thread = Thread(target=record_audio, args=(out_file, stop_event))
    thread.start()

    try:
        print("Recording... (Press ENTER to finish, ESC to cancel)", end="", flush=True)
        try:
            while True:
                key = getch()
                if key in ["\r", "\n"]:
                    print()
                    break
                if key == "\x1b":
                    print("\nCancelled")
                    return None
        except KeyboardInterrupt:
            print("\nCancelled")
            return None
        finally:
            stop_event.set()
            thread.join()

        if not os.path.exists(out_file) or os.path.getsize(out_file) == 0:
            return None

        print("Converting audio to text...")
        return convert(out_file)
    finally:
        if os.path.exists(out_file):
            os.remove(out_file)


def speech_to_text(
    local: bool = False,
) -> Optional[str]:
    if local:
        return _record_and_convert(ai.whisper.speech_to_text.convert_audio_to_text)
    return _record_and_convert(ai.openai.speech_to_text.convert_audio_to_text)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        help="Path to the output text file",
        default=None,
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Use the local whisper-cli backend instead of OpenAI",
    )
    parser.add_argument("--file", type=str, help="Transcribe an existing audio file")
    args = parser.parse_args()

    if args.file:
        if args.local:
            text = ai.whisper.speech_to_text.convert_audio_to_text(args.file)
        else:
            text = ai.openai.speech_to_text.convert_audio_to_text(args.file)
    else:
        text = speech_to_text(local=args.local)
    if text is not None:
        print(text)

        if args.output:
            with open(args.output, "w") as f:
                f.write(text)
