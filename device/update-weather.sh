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
# reMarkable OS 5.x loads the sleep image once, when xochitl starts, and then
# keeps showing that copy -- replacing the file changes nothing until the UI
# restarts. Confirmed on 5.8.203: the screen was stuck on an old forecast
# while sleep.png already matched what GitHub had published. Restarting only
# happens when the image actually changed, so at most a few times a day, and
# only while the tablet is awake and online. Set to 0 if a future OS picks up
# the file on its own.
RESTART_XOCHITL=1

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

# sanity check: must be a PNG (signature in the first bytes) and not tiny.
# NOTE: the tablet's busybox head has no -c and its od has no -A, so the obvious
# "head -c 4 | od -An -c" spelling silently fails and rejects every good image.
if ! dd if="$TMP" bs=8 count=1 2>/dev/null | grep -q PNG || [ "$(wc -c < "$TMP")" -lt 10000 ]; then
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
