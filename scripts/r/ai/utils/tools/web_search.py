import argparse
import re
import subprocess
import urllib.parse
from html.parser import HTMLParser

from utils.menu.textmenu import TextMenu


class SearchRetryMenu(TextMenu):
    def __init__(self, error_message: str, prompt: str):
        super().__init__(
            text=error_message,
            prompt=f"{prompt}\n([r]etry, [d]ebug)",
            prompt_color="red",
        )
        self.should_retry = False
        self.add_command(self._retry, hotkey="r")
        self.add_command(self._debug, hotkey="d")

    def _retry(self):
        self.should_retry = True
        self.close()

    def _debug(self):
        self.run_raw(lambda: subprocess.run(["browsercli", "inspect"]))


class _DuckDuckGoResultsParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.results: list[dict[str, str]] = []
        self.current: dict[str, str] | None = None
        self.field: str | None = None
        self.field_tag: str | None = None
        self.field_depth = 0
        self.buffer: list[str] = []

    @staticmethod
    def _classes(attrs) -> set[str]:
        return set(dict(attrs).get("class", "").split())

    def handle_starttag(self, tag: str, attrs):
        classes = self._classes(attrs)
        if tag == "a" and "result-link" in classes:
            if self.current:
                self.results.append(self.current)
            self.current = {"url": dict(attrs).get("href", "")}
            self.field = "title"
        elif self.current is not None and "result-snippet" in classes:
            self.field = "snippet"
        elif self.field:
            self.field_depth += 1
            return
        else:
            return

        self.field_tag = tag
        self.field_depth = 1
        self.buffer = []

    def handle_endtag(self, tag: str):
        if not self.field:
            return
        self.field_depth -= 1
        if self.field_depth or tag != self.field_tag:
            return
        assert self.current is not None
        self.current[self.field] = re.sub(r"\s+", " ", "".join(self.buffer)).strip()
        self.field = None
        self.field_tag = None
        self.buffer = []

    def handle_data(self, data: str):
        if self.field:
            self.buffer.append(data)

    def finish(self) -> list[dict[str, str]]:
        if self.current:
            self.results.append(self.current)
            self.current = None
        return self.results


class _GoogleResultsParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.results: list[dict[str, str]] = []
        self.link_url: str | None = None
        self.link_depth = 0
        self.title_depth = 0
        self.title_buffer: list[str] = []
        self.snippet_depth = 0
        self.snippet_buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs):
        if self.snippet_depth:
            self.snippet_depth += 1
            return

        if self.link_url is not None:
            self.link_depth += 1
            if tag == "h3":
                self.title_depth = 1
                self.title_buffer = []
            elif self.title_depth:
                self.title_depth += 1
            return

        attributes = dict(attrs)
        if attributes.get("data-sncf") == "1" and self.results:
            self.snippet_depth = 1
            self.snippet_buffer = []
            return

        if tag != "a":
            return
        href = dict(attrs).get("href", "")
        destination = _google_destination_url(href)
        if destination:
            self.link_url = destination
            self.link_depth = 1

    def handle_endtag(self, tag: str):
        if self.snippet_depth:
            self.snippet_depth -= 1
            if not self.snippet_depth:
                snippet = re.sub(
                    r"\s+", " ", "".join(self.snippet_buffer)
                ).strip()
                if snippet:
                    self.results[-1]["snippet"] = snippet
                self.snippet_buffer = []
            return

        if self.link_url is None:
            return

        if self.title_depth:
            self.title_depth -= 1
            if not self.title_depth and tag == "h3":
                title = re.sub(r"\s+", " ", "".join(self.title_buffer)).strip()
                if title:
                    self.results.append({"title": title, "url": self.link_url})

        self.link_depth -= 1
        if not self.link_depth:
            self.link_url = None

    def handle_data(self, data: str):
        if self.snippet_depth:
            self.snippet_buffer.append(data)
        elif self.title_depth:
            self.title_buffer.append(data)


def _destination_url(url: str) -> str:
    if url.startswith("//"):
        url = "https:" + url
    parsed = urllib.parse.urlparse(url)
    destination = urllib.parse.parse_qs(parsed.query).get("uddg")
    return destination[0] if destination else url


def _google_destination_url(url: str) -> str | None:
    if url.startswith("/url?"):
        destination = urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("q")
        url = destination[0] if destination else ""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return None
    if parsed.netloc == "google.com" or parsed.netloc.endswith(".google.com"):
        return None
    return url


def extract_search_results(html: str) -> str:
    parser = _DuckDuckGoResultsParser()
    parser.feed(html)
    results = parser.finish()
    if not results:
        raise ValueError("No DuckDuckGo search results found in page HTML")

    sections = []
    for index, result in enumerate(results, 1):
        lines = [f"{index}. {result.get('title', '')}", _destination_url(result["url"])]
        if result.get("snippet"):
            lines.append(result["snippet"])
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


def extract_google_search_results(html: str) -> str:
    parser = _GoogleResultsParser()
    parser.feed(html)
    if not parser.results:
        raise ValueError("No Google search results found in page HTML")

    sections = []
    for index, result in enumerate(parser.results, 1):
        lines = [f"{index}. {result['title']}", result["url"]]
        if result.get("snippet"):
            lines.append(result["snippet"])
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


def _fetch_search_html(url: str) -> str:
    while True:
        open_result = subprocess.run(
            ["browsercli", "open", url],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        if open_result.returncode == 0:
            result = subprocess.run(
                ["browsercli", "get-html"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
        else:
            result = open_result

        if result.returncode == 0 and result.stdout:
            return result.stdout

        retry_menu = SearchRetryMenu(
            error_message=result.stdout,
            prompt=f"failed to search {url}",
        )
        retry_menu.exec()
        if not retry_menu.should_retry:
            raise Exception(result.stdout)


def web_search(query: str, engine: str = "duckduckgo") -> str:
    """Perform web searches to gather information for user questions.
    - You can call this tool multiple times to gather enough information.
    - Start with broader queries to get an overview, then narrow down with more specific queries based on the results you receive.
    - Your query should be keywords (not full sentences) and SEO-friendly.
    """

    encoded_query = urllib.parse.quote_plus(query)
    if engine == "google":
        url = f"https://www.google.com/search?q={encoded_query}&udm=14&hl=en"
        extract_results = extract_google_search_results
    elif engine == "duckduckgo":
        url = f"https://lite.duckduckgo.com/lite/?q={encoded_query}"
        extract_results = extract_search_results
    else:
        raise ValueError(f"Unsupported search engine: {engine}")
    html = _fetch_search_html(url)
    return extract_results(html)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument(
        "-e",
        "--engine",
        choices=("google", "duckduckgo"),
        default="duckduckgo",
        help="search engine to use (default: duckduckgo)",
    )
    args = parser.parse_args()
    print(web_search(args.query, engine=args.engine))
