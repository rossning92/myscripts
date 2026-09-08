next_available_zip() {
    local requested="$1"
    local stem="${requested%.zip}"
    local candidate="$requested"
    local number=2

    while [ -e "$candidate" ]; do
        candidate="${stem}_${number}.zip"
        number=$((number + 1))
    done

    printf '%s\n' "$candidate"
}

if [ $# -eq 1 ] && [ -d "$1" ]; then
    folder="$(basename "${1%/}")"
    parent="$(dirname "${1%/}")"
    zipfile="$folder.zip"
    output="$(next_available_zip "$(pwd)/$zipfile")"
    cd "$parent" || exit 1
    zip -r "$output" "$folder"
else
    cwd="$(pwd -P)"
    zipfile="$(next_available_zip "$(basename "$cwd").zip")"
    inputs=()

    for input in "$@"; do
        case "$input" in
            "$cwd"/*) inputs+=("${input#"$cwd"/}") ;;
            *) inputs+=("$input") ;;
        esac
    done

    zip -r "$zipfile" "${inputs[@]}"
fi
