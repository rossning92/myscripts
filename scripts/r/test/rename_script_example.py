from _ext import rename_script
from _script import find_script

if __name__ == "__main__":
    script_full_path = find_script("r/confirm_.sh")
    rename_script(script_full_path, replace_all_occurrence=True)