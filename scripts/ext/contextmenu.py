import argparse
import http.client
import json
import urllib.parse
from dataclasses import dataclass
from typing import List

from _script import Script
from utils.menu import Menu


@dataclass
class _MatchedScript:
    name: str
    path: str
    match: str

    def __str__(self) -> str:
        return f"{self.name} {self.match}"


def _match_scripts_with_param(param: str) -> List[_MatchedScript]:
    encoded_param = urllib.parse.quote(param)
    host = "127.0.0.1:4312"
    path = f"/scripts/{encoded_param}"
    conn = http.client.HTTPConnection(host)
    try:
        conn.request("GET", path)
        response = conn.getresponse()
        if response.status == 200:
            data = response.read().decode("utf-8")
            json_data = json.loads(data)
            return [
                _MatchedScript(
                    name=script["name"],
                    path=script["path"],
                    match=script["match"],
                )
                for script in json_data["scripts"]
            ]
        else:
            raise Exception(f"Failed to retrieve data: {response.status}")
    finally:
        conn.close()


class ContextMenu(Menu[_MatchedScript]):
    def __init__(self, param: str, **kwargs):
        super().__init__(
            prompt="open with",
            items=_match_scripts_with_param(param),
            quick_select=True,
            **kwargs,
        )

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("param", type=str)
    args = parser.parse_args()

    menu = ContextMenu(param=args.param)
    menu.exec()

    selected_script = menu.get_selected_item()
    if selected_script is not None:
        script = Script(selected_script.path)
        script.execute(args=[selected_script.match], cd=False)
