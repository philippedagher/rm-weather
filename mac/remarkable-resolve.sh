#!/bin/sh
# Resolve the reMarkable's current Wi-Fi address by MAC, then hand the socket to
# ssh. Used as a ProxyCommand from ~/.ssh/config so "ssh remarkable" keeps
# working when DHCP moves the tablet (it has already gone .37 -> .33).
#
# Usage: remarkable-resolve.sh <port>
set -u

MAC="aa:bb:cc:dd:ee:ff"        # YOUR tablet: arp -an | grep -i <vendor prefix>
FALLBACK="192.168.1.100"      # last address seen, tried if discovery fails
PORT="${1:-22}"
IFACE="${REMARKABLE_IFACE:-en0}"

# macOS prints ARP MACs with leading zeros stripped per octet ("e4:f2:0"), so
# both sides are normalised to two hex digits before comparing.
find_ips() {
    arp -an 2>/dev/null | awk -v want="$MAC" '
        {
            n = split($4, o, ":")
            if (n != 6) next
            full = ""
            for (i = 1; i <= 6; i++) {
                p = o[i]
                if (length(p) < 2) p = "0" p
                full = full (i > 1 ? ":" : "") p
            }
            if (tolower(full) == tolower(want)) {
                ip = $2
                gsub(/[()]/, "", ip)
                print ip
            }
        }'
}

# A sleeping reMarkable drops off the network entirely, so an empty cache is
# normal rather than an error. Sweep the local /24 to provoke ARP replies.
prime_cache() {
    base=$(ipconfig getifaddr "$IFACE" 2>/dev/null | sed 's/\.[0-9]*$//')
    [ -z "$base" ] && return
    i=1
    while [ "$i" -le 254 ]; do
        ping -c 1 -t 1 "$base.$i" >/dev/null 2>&1 &
        i=$((i + 1))
    done
    wait
}

# An ARP entry outlives the tablet going to sleep, and the address it names can
# by then belong to something else, so a hit is confirmed before use.
# macOS nc exits 0 from -z even when the connection fails, so its exit status is
# useless here; the verbose line is what actually reports the outcome.
reachable() {
    nc -z -G 2 -v "$1" "$PORT" 2>&1 | grep -q succeeded
}

# After the tablet moves, the cache can hold both the stale entry and the new
# one under the same MAC, so every candidate is tried rather than just the first.
pick() {
    for candidate in $(find_ips); do
        if reachable "$candidate"; then
            echo "$candidate"
            return 0
        fi
    done
    return 1
}

IP=$(pick) || {
    prime_cache
    IP=$(pick) || IP=""
}
[ -z "$IP" ] && IP="$FALLBACK"

# Progress goes to stderr: stdout is the ssh data channel and must stay clean.
echo "remarkable: $IP" >&2
exec nc "$IP" "$PORT"
