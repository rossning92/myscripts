#!/usr/bin/env bash
set -euo pipefail

get_location() {
    local ip=$1

    curl -fsS --max-time 3 \
        "https://ipwho.is/$ip?fields=success,city,region,country" |
        jq -er 'select(.success) | [.city, .region, .country] | map(select(. != null and . != "")) | join(", ")' \
        2>/dev/null
}

get_connected_since() {
    local ip=$1 session host timestamp epoch
    local newest=0 since=""

    while read -r session _; do
        host=$(loginctl show-session "$session" -p RemoteHost --value)
        [[ "$host" == "$ip" ]] || continue

        timestamp=$(loginctl show-session "$session" -p Timestamp --value)
        epoch=$(date -d "$timestamp" +%s)

        if ((epoch > newest)); then
            newest=$epoch
            since=$(date -d "$timestamp" '+%F %R')
        fi
    done < <(loginctl list-sessions --no-legend)

    printf '%s' "$since"
}

connections=$(ss -Htn state established | awk '
function port(address) {
    sub(/^.*:/, "", address)
    return address
}

{
    local_port = port($3)

    if (local_port == 22)
        service = "ssh"
    else if (local_port == 2022)
        service = "et"
    else
        next

    print service "\t" $4
}
')

if [[ -z "$connections" ]]; then
    echo "No remote shells connected."
    exit
fi

printf "%-8s %-24s %-16s %s\n" "SERVICE" "REMOTE" "SINCE" "LOCATION"

while IFS=$'\t' read -r service remote; do
    ip=${remote%:*}
    ip=${ip#[}
    ip=${ip%]}

    since=$(get_connected_since "$ip")
    location=$(get_location "$ip") || location=""

    printf "%-8s %-24s %-16s %s\n" "$service" "$remote" "$since" "$location"
done <<< "$connections"
