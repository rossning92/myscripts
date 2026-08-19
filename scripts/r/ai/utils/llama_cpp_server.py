import os
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

from utils.menu import Menu
from utils.menu.confirmmenu import confirm
from utils.spinner import Spinner

_DEFAULT_ENDPOINT = "http://127.0.0.1:8080/v1/chat/completions"
_START_COMMAND = ["start_script", "r/ai/llama_server.sh"]
_START_TIMEOUT_SECONDS = 60


def _is_server_available() -> bool:
    endpoint = os.environ.get("LLAMA_CPP_ENDPOINT", _DEFAULT_ENDPOINT)
    parsed_endpoint = urllib.parse.urlsplit(endpoint)
    health_endpoint = urllib.parse.urlunsplit(
        (parsed_endpoint.scheme, parsed_endpoint.netloc, "/health", "", "")
    )
    try:
        with urllib.request.urlopen(health_endpoint, timeout=0.5):
            return True
    except urllib.error.HTTPError as error:
        # llama.cpp returns 503 from /health while the model is still loading.
        error.close()
        return False
    except (OSError, urllib.error.URLError):
        return False


class _WaitForServerMenu(Menu):
    def __init__(self) -> None:
        self.__prompt = "waiting for llama.cpp server..."
        super().__init__(
            prompt=self.__prompt,
            search_mode=False,
            line_number=False,
            timeout_sec=0.1,
        )
        self.__available = False
        self.__deadline = time.monotonic() + _START_TIMEOUT_SECONDS
        self.__spinner = Spinner()

    def on_timeout(self) -> None:
        if _is_server_available():
            self.__available = True
            self.close()
        elif time.monotonic() >= self.__deadline:
            self.close()
        else:
            self.set_prompt(f"{self.__prompt} {self.__spinner.frame}")
            self.__spinner.advance()

    def is_available(self) -> bool:
        return self.__available


def ensure_llama_cpp_server() -> bool:
    if _is_server_available():
        return True
    if not confirm("llama.cpp server is unavailable. Start it?"):
        return False

    subprocess.Popen(_START_COMMAND)
    wait_menu = _WaitForServerMenu()
    wait_menu.exec()
    return wait_menu.is_available()
