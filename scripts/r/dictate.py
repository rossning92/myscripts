import os
import subprocess
import tkinter as tk
from threading import Event, Thread

import ai.openai.speech_to_text
from audio.record_audio import record_audio


def get_active_window() -> str:
    return subprocess.check_output(["xdotool", "getactivewindow"], text=True).strip()


def create_status_window(text: str) -> tk.Tk:
    root = tk.Tk()
    try:
        root.withdraw()
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        label = tk.Label(root, text=text)
        label.pack(padx=22, pady=14)
        root.update_idletasks()

        width = root.winfo_reqwidth()
        height = root.winfo_reqheight()
        x = (root.winfo_screenwidth() - width) // 2
        bottom_margin = round(root.winfo_fpixels("0.5i"))
        y = max(0, root.winfo_screenheight() - height - bottom_margin)
        root.geometry(f"{width}x{height}+{x}+{y}")
        root.deiconify()
        root.wait_visibility()
        return root
    except BaseException:
        root.destroy()
        raise


def wait_for_confirmation() -> bool:
    root = create_status_window("Listening... (F8: confirm | Esc: cancel)")
    confirmed = False

    def finish(value: bool) -> None:
        nonlocal confirmed
        confirmed = value
        root.quit()

    try:
        root.bind("<F8>", lambda _event: finish(True))
        root.bind("<Escape>", lambda _event: finish(False))

        root.focus_force()
        root.grab_set_global()
        root.mainloop()
        return confirmed
    finally:
        try:
            root.grab_release()
        except tk.TclError:
            pass
        root.destroy()


def transcribe_with_status(audio_file: str) -> str:
    size_kb = os.path.getsize(audio_file) / 1024
    root = create_status_window(f"Transcribing... (size: {size_kb:.0f}k)")
    result: dict[str, object] = {}

    try:

        def transcribe() -> None:
            try:
                result["text"] = ai.openai.speech_to_text.convert_audio_to_text(
                    audio_file
                )
            except BaseException as error:
                result["error"] = error

        worker = Thread(target=transcribe)
        worker.start()

        def check_worker() -> None:
            if worker.is_alive():
                root.after(50, check_worker)
            else:
                root.quit()

        root.after(50, check_worker)
        root.mainloop()
        worker.join()

        if "error" in result:
            raise result["error"]
        return str(result.get("text", ""))
    finally:
        root.destroy()


def dictate() -> None:
    target_window = get_active_window()
    stop_event = Event()
    audio_file = ""

    def record() -> None:
        nonlocal audio_file
        audio_file = record_audio(stop_event=stop_event)

    recording = Thread(target=record)
    recording.start()

    try:
        try:
            confirmed = wait_for_confirmation()
        finally:
            stop_event.set()
            recording.join()

        if not confirmed or not audio_file or os.path.getsize(audio_file) == 0:
            return

        text = transcribe_with_status(audio_file)

        if text:
            subprocess.run(
                ["xdotool", "windowactivate", "--sync", target_window],
                check=True,
            )
            subprocess.run(
                ["xdotool", "type", "--clearmodifiers", "--delay", "1", "--", text],
                check=True,
            )
    finally:
        if recording.is_alive():
            stop_event.set()
            recording.join()
        if audio_file and os.path.exists(audio_file):
            os.remove(audio_file)


if __name__ == "__main__":
    dictate()
