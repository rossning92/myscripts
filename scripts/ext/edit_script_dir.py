from utils.editor import open_code_editor
from utils.script.path import get_script_dirs_config_file

if __name__ == "__main__":
    open_code_editor(get_script_dirs_config_file())
