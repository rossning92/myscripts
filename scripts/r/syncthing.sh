set -e
syncthing generate
exec syncthing --no-browser
