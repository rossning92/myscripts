#!/bin/bash
for file in "$@"; do
    echo "Rotate image: $file"
    if [[ -n "${BACKUP_IMAGE}" ]]; then
        cp "$file" "$file.bak"
    fi
    magick "$file" -rotate 180 "$file"
done
