import argparse
import json
import os
import urllib.error
import urllib.request
import uuid


def _search_url(base_url: str) -> str:
    base_url = base_url.rstrip("/")
    if base_url.endswith("/v1"):
        return f"{base_url}/alpha/search"
    return f"{base_url}/v1/alpha/search"


def _format_results(results: list[object]) -> str:
    sections = []
    for result in results:
        if not isinstance(result, dict):
            continue
        title = result.get("title")
        url = result.get("url")
        if not isinstance(title, str) or not isinstance(url, str):
            continue
        lines = [f"{len(sections) + 1}. {title}", url]
        snippet = result.get("snippet")
        if isinstance(snippet, str) and snippet:
            lines.append(snippet)
        sections.append("\n".join(lines))

    if not sections:
        raise ValueError("No search results returned by CLI Proxy API")
    return "\n\n".join(sections)


def web_search(query: str, model: str = "gpt-5.6-sol") -> str:
    base_url = os.environ.get("CLIPROXY_BASE_URL", "http://127.0.0.1:8317/v1")
    api_key = os.environ.get("CLIPROXY_API_KEY", "myscripts-local-key")
    payload = {
        "id": str(uuid.uuid4()),
        "model": model,
        "commands": {"search_query": [{"q": query}]},
    }
    request = urllib.request.Request(
        _search_url(base_url),
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Originator": "codex_cli_rs",
            "User-Agent": "codex_cli_rs",
            "Session_id": str(uuid.uuid4()),
            "X-Client-Request-Id": str(uuid.uuid4()),
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            body = json.load(response)
    except urllib.error.HTTPError as error:
        message = error.read().decode("utf-8", "replace")
        raise RuntimeError(
            f"CLI Proxy API search failed with HTTP {error.code}\n{message}"
        ) from error

    results = body.get("results")
    if not isinstance(results, list):
        raise ValueError("CLI Proxy API response has no results array")
    return _format_results(results)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("--model", default="gpt-5.6-sol")
    args = parser.parse_args()
    print(web_search(args.query, model=args.model))
