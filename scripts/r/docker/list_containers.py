import subprocess

from utils.menu import Menu
from utils.menu.confirmmenu import confirm


class ContainerMenu(Menu):
    def __init__(self):
        super().__init__(selected_index=1)
        self.add_command(self.__delete_container, hotkey="delete")
        self.__refresh_containers()

    def __delete_container(self):
        selected = self.get_selected_item()
        if not selected:
            return

        parts = selected.split()
        if not parts or parts[0] == "CONTAINER":
            return

        container_id = parts[0]
        if confirm(f"Delete container {container_id}?", prompt_color="red"):
            subprocess.check_output(["docker", "rm", "-f", container_id])
            self.__refresh_containers()

    def __refresh_containers(self):
        self.items[:] = subprocess.check_output(
            [
                "docker",
                "ps",
                "-a",
                "--format",
                "table {{.ID}}\t{{.Image}}\t{{.Status}}",
            ],
            universal_newlines=True,
        ).splitlines()
        self.refresh()


if __name__ == "__main__":
    ContainerMenu().exec()
