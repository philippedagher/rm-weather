#!/bin/sh
# Run this ON the reMarkable (as root) from the directory containing the 3 files:
#   update-weather.sh  weather.service  weather.timer
set -e
mkdir -p /home/root/weather
cp update-weather.sh /home/root/weather/update-weather.sh
chmod +x /home/root/weather/update-weather.sh
cp weather.service weather.timer /etc/systemd/system/
# Keep a copy on the home partition. An OS update replaces /etc and /usr
# wholesale -- the timer and service vanish and the sleep screen quietly stops
# refreshing -- but /home/root survives, so reinstalling needs nothing from the
# Mac: just run  sh /home/root/weather/reinstall.sh
cp weather.service weather.timer /home/root/weather/
cat > /home/root/weather/reinstall.sh <<'REINSTALL'
#!/bin/sh
# Re-run after a reMarkable OS update, which wipes /etc/systemd/system.
set -e
cp /home/root/weather/weather.service /home/root/weather/weather.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now weather.timer
sh /home/root/weather/update-weather.sh || true
echo "reinstalled; next run:"; systemctl list-timers weather.timer --no-pager | head -n 2
REINSTALL
chmod +x /home/root/weather/reinstall.sh
systemctl daemon-reload
systemctl enable --now weather.timer
# first download right now
/home/root/weather/update-weather.sh || true

# point xochitl at our file (OS 3.2-3.13 or 3.20+); done with xochitl stopped so it
# does not overwrite the config file on exit
CONF=/home/root/.config/remarkable/xochitl.conf
cp "$CONF" "$CONF.bak-$(date +%s)"
systemctl stop xochitl
if grep -q '^SleepScreenPath=' "$CONF"; then
    sed -i 's#^SleepScreenPath=.*#SleepScreenPath=/home/root/weather/sleep.png#' "$CONF"
elif grep -q '^\[General\]' "$CONF"; then
    sed -i 's#^\[General\]#[General]\nSleepScreenPath=/home/root/weather/sleep.png#' "$CONF"
else
    printf '\n[General]\nSleepScreenPath=/home/root/weather/sleep.png\n' >> "$CONF"
fi
systemctl start xochitl
echo "Done. Timer status:"; systemctl list-timers weather.timer --no-pager
