import os
import sys
import threading
import time

from fswatch import watch_directory

WATCH_PATH = sys.argv[1] if len(sys.argv) > 1 else "."
TEST_FILE = os.path.join(WATCH_PATH, "fswatch_test_tmp.txt")


def run_test(stop_event):
    time.sleep(2)
    print(f"\n--- Creating {TEST_FILE}", flush=True)
    with open(TEST_FILE, "w") as f:
        f.write("hello\n")
    time.sleep(2)

    print(f"\n--- Modifying {TEST_FILE}", flush=True)
    with open(TEST_FILE, "a") as f:
        f.write("world\n")
    time.sleep(2)

    print(f"\n--- Deleting {TEST_FILE}", flush=True)
    os.remove(TEST_FILE)
    time.sleep(2)

    print("\n--- Test complete!", flush=True)
    stop_event.set()


if __name__ == "__main__":
    print(f"Monitoring: {WATCH_PATH}", flush=True)

    stop_event = threading.Event()

    t = threading.Thread(target=run_test, args=(stop_event,), daemon=True)
    t.start()

    # watch_directory is blocking (synchronous ReadDirectoryChangesW),
    # so we run it in a thread and stop when test is done.
    def watcher():
        for action, filepath in watch_directory(
            WATCH_PATH, recursive=False, stop_event=stop_event
        ):
            print(f"[{action:12s}] {filepath}", flush=True)

    wt = threading.Thread(target=watcher, daemon=True)
    wt.start()

    t.join()
    # Give watcher a moment to process final events
    time.sleep(1)
    print("Done.", flush=True)
