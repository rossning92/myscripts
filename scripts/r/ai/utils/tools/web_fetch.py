import argparse
import subprocess

from utils.menu.textmenu import TextMenu


class FetchRetryMenu(TextMenu):
    def __init__(self, error_message: str, prompt: str):
        super().__init__(
            text=error_message,
            prompt=prompt,
            prompt_color="red",
        )
        self.should_retry = False
        self.add_command(self._retry, hotkey="r", name="retry", pinned=True)
        self.add_command(self._debug, hotkey="d", name="debug", pinned=True)

    def _retry(self):
        self.should_retry = True
        self.close()

    def _debug(self):
        self.run_raw(
            lambda: subprocess.run(
                ["run_script", "r/web/browsercli/browsercli.js", "inspect"]
            )
        )


def web_fetch(url: str) -> str:
    """
    Fetch the content of a web page from the given URL.
    """
    while True:
        result = subprocess.run(
            [
                "run_script",
                "r/web/browsercli/browsercli.js",
                "get-markdown",
                url,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        returncode = result.returncode
        stdout = result.stdout

        if returncode == 0 and stdout:
            return stdout

        error_message = stdout
        retry_menu = FetchRetryMenu(
            error_message=error_message,
            prompt=f"failed to fetch {url}",
        )
        retry_menu.exec()
        if not retry_menu.should_retry:
            raise Exception(error_message)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    args = parser.parse_args()
    print(web_fetch(args.url))
