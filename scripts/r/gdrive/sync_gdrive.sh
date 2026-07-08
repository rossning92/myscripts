set -e

if [[ -z "$GDRIVE_DIR" ]]; then
    echo 'ERROR: GDRIVE_DIR cannot be empty.'
    exit 1
fi

source "$(dirname "$0")/_init_rclone.sh"

cd "$HOME"

rclone_wrapper() {
    logfile="$(mktemp)"
    echo "Log file: $logfile"
    local_dir="$2"

    extra_args=''
    if [[ -n "$SYNCGDRIVE_DRYRUN" ]]; then
        extra_args+=' --dry-run'
    fi
    if [[ ! -d "$local_dir" ]]; then
        extra_args+=' --resync'
        mkdir "$local_dir"
    fi
    if [[ -n "$SYNCGDRIVE_RESYNC" ]]; then
        extra_args+=' --resync'
    fi

    rclone bisync "drive:$1" "$local_dir" \
        --color NEVER \
        --verbose \
        --ignore-checksum \
        --max-lock 2m \
        --recover \
        --resilient \
        --exclude=__pycache__/** \
        --exclude=.config/** \
        --exclude=.git \
        --exclude=.mypy_cache/** \
        --exclude=node_modules/** \
        --exclude=tmp/** \
        --conflict-resolve newer \
        $extra_args \
        "${@:3}" \
        2>&1 | tee "$logfile"
    ret=${PIPESTATUS[0]}
    if [[ "$ret" != "0" ]]; then
        echo "ERROR: rclone returned $ret"
        if [[ "$ret" == 7 ]] && grep -Eiq 'rate limit|ratelimit|quota exceeded|user rate limit' "$logfile"; then
            echo 'ERROR: Rate limit exceeded'
            exit 0
        elif grep -Eiq 'cannot find prior Path1 or Path2 listings|cannot find prior Path[12]|prior Path[12].*listings|Path1: .*\.path1\.lst|Path2: .*\.path2\.lst' "$logfile"; then
            read -r -p "Prior bisync listings are missing. Resync? (y/n): " ans
            if [[ "$ans" =~ ^[Yy]$ ]]; then
                rclone_wrapper "$@" --resync
            else
                return 1
            fi
        elif grep -Eiq '(^|[[:space:]])--force([[:space:]]|$)|force' "$logfile"; then
            read -r -p "Force sync? (y/n): " ans
            if [[ "$ans" =~ ^[Yy]$ ]]; then
                rclone_wrapper "$@" --force
            else
                return 1
            fi
        elif grep -Eiq '(^|[[:space:]])--resync([[:space:]]|$)|resync' "$logfile"; then
            read -r -p "Resync? (y/n): " ans
            if [[ "$ans" =~ ^[Yy]$ ]]; then
                rclone_wrapper "$@" --resync
            else
                return 1
            fi
        else
            return 1
        fi
    fi
}

[[ ! -d "$HOME/gdrive" ]] && mkdir -p "$HOME/gdrive"
[[ -z "$LOCAL_DIR" ]] && local_dir="$HOME/gdrive/$GDRIVE_DIR" || local_dir="$LOCAL_DIR"
[[ -x "$(command -v cygpath)" ]] && local_dir="$(cygpath -w "$local_dir")" # convert to win path

echo "Sync \"gdrive://$GDRIVE_DIR\" <=> \"$local_dir\""
rclone_wrapper "$GDRIVE_DIR" "$local_dir"
