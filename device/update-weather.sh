#!/bin/sh
# Runs ON the reMarkable 2. Downloads the latest rendered weather.png and
# installs it as the sleep screen.
#
# The URL below points at this repo's "output" branch, which the GitHub Actions
# workflow force-pushes a fresh weather.png to. Change it only for a fork/rename:
#   https://raw.githubusercontent.com/<USER>/<REPO>/output/weather.png

URL="https://raw.githubusercontent.com/philippedagher/rm-weather/output/weather.png"
DEST="/home/root/weather/sleep.png"        # referenced by SleepScreenPath in xochitl.conf
LEGACY="/usr/share/remarkable/suspended.png" # also overwritten, for OS versions that ignore SleepScreenPath
RESTART_XOCHITL=0   # set to 1 ONLY if testing shows the old image sticks until reboot

TMP="$DEST.tmp"
mkdir -p "$(dirname "$DEST")"

# download (busybox wget on stock firmware; curl if present).
# Up to 6 attempts 10 s apart: the timer may fire before Wi-Fi is back after wake-up.
download() {
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL -o "$TMP" "$URL"
    else
        wget -q -O "$TMP" "$URL"
    fi
}
i=0
until download; do
    i=$((i+1)); rm -f "$TMP"
    [ $i -ge 6 ] && { echo "download failed"; exit 1; }
    sleep 10
done

# sanity check: must be a PNG (starts with the PNG signature) and not tiny
if [ "$(head -c 4 "$TMP" | od -An -c | tr -d ' ')" != "211PNG" ] || [ "$(wc -c < "$TMP")" -lt 10000 ]; then
    echo "downloaded file is not a valid PNG"; rm -f "$TMP"; exit 1
fi

# skip if unchanged
if [ -f "$DEST" ] && cmp -s "$TMP" "$DEST"; then
    rm -f "$TMP"; echo "unchanged"; exit 0
fi

mv -f "$TMP" "$DEST"
cp -f "$DEST" "$LEGACY" 2>/dev/null || true   # rM2 rootfs is writable; harmless if it fails
echo "sleep screen updated $(date)"

if [ "$RESTART_XOCHITL" = "1" ]; then
    systemctl restart xochitl
fi
