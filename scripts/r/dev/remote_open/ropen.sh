#!/usr/bin/env bash
# Compatibility entry point; the ropen client is now implemented in Python.
exec "$(dirname "$(readlink -f "$0")")/ropen.py" "$@"
