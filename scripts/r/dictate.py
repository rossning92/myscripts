import os
import traceback
from threading import Event, Thread

import ai.openai.speech_to_text
from audio.record_audio import record_audio
from pynput import keyboard
from utils.hotkey import wait_for_global_hotkeys
from utils.notify import send_notify


def type_text(text: str) -> None:
    keyboard.Controller().type(text)


def dictate() -> None:
    stop_event = Event()
    audio_file = ""

    def record() -> None:
        nonlocal audio_file
        audio_file = record_audio(stop_event=stop_event)

    recording = Thread(target=record)
    recording.start()

    try:
        send_notify("Listening... (F8: transcribe | F9: cancel)", app="Dictation")
        pressed = wait_for_global_hotkeys(("F8", "F9"))
        stop_event.set()
        recording.join()

        if pressed.lower() == "f9":
            send_notify("Cancelled", app="Dictation")
            return

        if not audio_file or os.path.getsize(audio_file) == 0:
            send_notify("No audio recorded", app="Dictation")
            return

        size_kb = os.path.getsize(audio_file) / 1024
        send_notify(f"Transcribing... ({size_kb:.0f} KB)", app="Dictation")
        text = ai.openai.speech_to_text.convert_audio_to_text(audio_file)
        if text:
            type_text(text)
            send_notify("Transcription inserted", app="Dictation")
        else:
            send_notify("No speech recognized", app="Dictation")
    finally:
        if recording.is_alive():
            stop_event.set()
            recording.join()
        if audio_file and os.path.exists(audio_file):
            os.remove(audio_file)


def _main() -> None:
    print("Dictation ready. Press F8 to start dictating.", flush=True)
    while True:
        wait_for_global_hotkeys("F8")
        try:
            dictate()
        except Exception:
            # A failed recording or transcription should not stop dictation.
            send_notify("Recording or transcription failed", app="Dictation")
            traceback.print_exc()


if __name__ == "__main__":
    _main()
