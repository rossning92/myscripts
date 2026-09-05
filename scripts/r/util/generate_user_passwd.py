#!/usr/bin/env python3

import secrets
import string
import sys

from utils.clip import set_clip
from utils.getch import getch


def generate_username(length=16):
    first_character = secrets.choice(string.ascii_lowercase)
    alphabet = string.ascii_lowercase + string.digits
    return first_character + "".join(
        secrets.choice(alphabet) for _ in range(length - 1)
    )


def generate_password(length=24):
    character_groups = (
        string.ascii_lowercase,
        string.ascii_uppercase,
        string.digits,
        "!@#$%^&*-_=+",
    )
    password = [secrets.choice(group) for group in character_groups]
    alphabet = "".join(character_groups)
    password.extend(secrets.choice(alphabet) for _ in range(length - len(password)))
    secrets.SystemRandom().shuffle(password)
    return "".join(password)


def main():
    username = generate_username()
    password = generate_password()
    interactive = sys.stdin.isatty() and sys.stdout.isatty()

    print(f"Username: {username}")
    print(f"Password: {password}")

    if not interactive:
        return

    print("\nu copy username  p copy password", end="", flush=True)
    while True:
        key = getch()
        key = key.lower() if key else ""

        if key == "u":
            set_clip(username)
            message = "Username copied"
            break
        if key == "p":
            set_clip(password)
            message = "Password copied"
            break

    print(f"\n{message}")


if __name__ == "__main__":
    main()
