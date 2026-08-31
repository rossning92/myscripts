import argparse
import subprocess


def web_fetch(url: str) -> str:
    """
    Fetch the content of a web page from the given URL.
    """
    open_result = subprocess.run(
        [
            "run_script",
            "r/web/browsercli/browsercli.js",
            "open",
            url,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if open_result.returncode == 0:
        result = subprocess.run(
            [
                "run_script",
                "r/web/browsercli/browsercli.js",
                "get-markdown",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    else:
        result = open_result

    if result.returncode == 0 and result.stdout:
        return result.stdout

    raise Exception(result.stdout)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    args = parser.parse_args()
    print(web_fetch(args.url))
