from ai.agent import AGENTS, DEFAULT_AGENT_FILE, get_default_agent
from utils.jsonutil import save_json
from utils.menu import Menu


def main() -> int:
    agents = list(AGENTS)
    current_agent = get_default_agent()
    menu = Menu(
        prompt="select default agent",
        items=agents,
        selected_index=agents.index(current_agent),
        enable_command_palette=False,
        quick_select=True,
    )
    menu.exec()
    agent = menu.get_selected_item()
    if agent is None:
        return 0

    save_json(DEFAULT_AGENT_FILE, {"agent": agent})
    print(f"Default agent set to {agent}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
