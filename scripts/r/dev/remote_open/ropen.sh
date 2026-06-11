#!/bin/bash
# Open a file or URL in the remote viewer browser.
#   ropen /path/to/image.png
#   ropen https://example.com
#   ropen relative/file.txt

PORT="${ROPEN_PORT:-8765}"
TARGET="$1"

if [[ -z "$TARGET" ]]; then
    echo "usage: ropen <file_or_url>" >&2
    exit 1
fi

curl -sf -X POST "http://localhost:${PORT}/api/open" \
    -d "path=$(printf '%s' "$TARGET" | sed 's/ /%20/g')&cwd=$(pwd)" \
    > /dev/null

if [[ $? -ne 0 ]]; then
    echo "error: could not reach server on port $PORT. is server.py running?" >&2
    exit 1
fi
