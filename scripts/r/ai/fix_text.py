import http.client
import json
import os
import ssl

from utils.clip import get_selection, set_clip


def _get_api_key() -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY environment variable is not set.")
    return api_key


def _complete_chat_oai(payload: dict, api_key: str) -> dict:
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    context = ssl.create_default_context()
    conn = http.client.HTTPSConnection("api.openai.com", context=context)
    try:
        conn.request("POST", "/v1/chat/completions", body=data, headers=headers)
        with conn.getresponse() as response:
            if response.status != 200:
                raise Exception(
                    f"HTTP Error {response.status}: {response.read().decode()}"
                )
            return json.loads(response.read().decode("utf-8"))
    finally:
        conn.close()


def _fix_text(text: str, api_key: str) -> str:
    payload = {
        "model": "gpt-6-luna",
        "messages": [
            {
                "role": "user",
                "content": (
                    "Fix the spelling and grammar of the following text and only return the corrected text:\n"
                    "-------\n"
                    f"{text}\n"
                    "-------"
                ),
            }
        ],
        "reasoning_effort": "low",
    }
    result = _complete_chat_oai(payload, api_key)
    return result["choices"][0]["message"]["content"].strip()


def main() -> None:
    text = get_selection()
    if not text.strip():
        return

    try:
        api_key = _get_api_key()
        print("request")
        out = _fix_text(text, api_key)
        print(out)
        set_clip(out)
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
