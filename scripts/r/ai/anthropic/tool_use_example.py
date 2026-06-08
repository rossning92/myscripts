from pprint import pprint

from ai.anthropic.chat import complete_chat
from ai.utils.message import Message
from utils.logger import setup_logger
from utils.printc import printc

setup_logger()


def get_weather(location: str) -> str:
    """Get the current weather in a given location."""
    # This is a placeholder implementation. Replace with actual weather fetching logic.
    printc(f"get_weather(): Fetching weather for {location}...", color="blue")
    return "75°F"


messages = [{"role": "user", "content": "What's the weather like in San Francisco?"}]
for s in complete_chat(
    messages,
    tools=[get_weather],
    on_tool_use=lambda data: globals()[data.tool_name](**data.args),
):
    printc(s, end="")
pprint(messages[-1]["content"])
