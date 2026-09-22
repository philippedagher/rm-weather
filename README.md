# reMarkable 2 weather sleep screen — Batroun, Lebanon

Next 24 h: rain probability, wind speed/gusts/direction, swell height/period/direction.
10 days: sky, temperatures, rain, wind (speed/gust/dir), swell (height/period/dir).
Rendered 4x a day by GitHub Actions from Open-Meteo weather + marine APIs (free, no key)
and pulled by the tablet over Wi-Fi 20 minutes later.

```
GitHub Actions at 06:00 / 12:00 / 16:00 / 21:00 Beirut  ──►  weather.png on branch "output"
                                                                    │
reMarkable 2 timer at 06:20 / 12:20 / 16:20 / 21:20  ◄──────────────┘  → /home/root/weather/sleep.png
xochitl.conf: SleepScreenPath=/home/root/weather/sleep.png
```

Swell comes from the Open-Meteo marine model at 34.243169, 35.658553
(`SEA_LAT/SEA_LON` in `render_weather.py`); arrows show where wind/swell travel TO,
the letters (W, NW…) the direction they come FROM, as in marine forecasts.

## Part A — the renderer on GitHub (once, ~5 minutes)

1. Create a new **public** repository on github.com, e.g. `rm-weather`
   (public is simplest: the tablet downloads the PNG without any token).
2. Upload the contents of this folder to it (drag-and-drop in the GitHub web UI
   works: `render_weather.py`, `fonts/`, `.github/workflows/weather.yml`, `README.md`).
   The `device/` folder can be uploaded too; it is only used on the tablet.
3. Open the **Actions** tab → *Render weather sleep screen* → **Run workflow**.
   After ~1 minute a branch named `output` appears containing `weather.png`.
4. Your image URL is now:
   <https://raw.githubusercontent.com/philippedagher/rm-weather/output/weather.png>
   Open it in a browser to check it.

Notes: GitHub cron runs in UTC and Lebanon changes between UTC+3 and UTC+2, so the
workflow is triggered at both possible UTC hours and a first step checks the Beirut
clock, doing the work only at 06, 12, 16 and 21 h (the other runs exit in seconds).
GitHub may start a run a few minutes late. It also pauses schedules in repos with no
commits for 60 days — any small commit or pressing *Run workflow* re-enables it.

## Part B — the tablet (once, ~10 minutes)

1. On the reMarkable: **Settings → Help → Copyrights and licenses**, scroll to
   *GPLv3 Compliance*: note the **password** for user `root`, and the IP address
   (over USB cable it is always `10.11.99.1`; over Wi-Fi it is the 192.168.x.x shown).
2. The `URL=` line in `device/update-weather.sh` is already pointed at
   <https://raw.githubusercontent.com/philippedagher/rm-weather/output/weather.png>,
   so there is nothing to edit. (Change it only if you rename or fork the repo.)
3. From a Terminal on your Mac, copy the four device files to the tablet:
   ```
   cd rm-weather/device
   scp update-weather.sh weather.service weather.timer install-on-device.sh root@10.11.99.1:/home/root/
   ```
4. Log in and run the installer:
   ```
   ssh root@10.11.99.1
   cd /home/root && sh install-on-device.sh
   ```
   It installs the script + timer, downloads the first image, backs up
   `xochitl.conf`, adds `SleepScreenPath=/home/root/weather/sleep.png`, and
   restarts the tablet UI (takes ~10 s).
5. Test: press the power button to put the tablet to sleep. The weather
   dashboard should be the sleep screen.

## Checking / troubleshooting (on the tablet, over SSH)

```
journalctl -u weather.service -n 20        # last download log
systemctl list-timers weather.timer         # when it runs next
sh /home/root/weather/update-weather.sh     # force an update now
ls -la /home/root/weather/                  # sleep.png should be ~80-120 KB
cat /etc/version                            # OS version
```

* Image never changes after the first one (only after a reboot)? Your OS version
  caches the sleep image. Edit `/home/root/weather/update-weather.sh` and set
  `RESTART_XOCHITL=1`: the UI restarts for ~10 s whenever a *new* image arrives
  (at most 4 times a day, and only when the tablet is awake and on Wi-Fi).
* OS 3.14–3.19 ignore `SleepScreenPath`; the script also overwrites
  `/usr/share/remarkable/suspended.png`, which works there, but that file is reset by
  every OS update — just re-run `sh /home/root/weather/update-weather.sh` after updating.
* While asleep the tablet has no Wi-Fi and no timers run. If it was asleep at 06:20
  (say), the missed run is caught up as soon as you wake it (`Persistent=true`), so the
  *next* sleep shows the 06:00 forecast. It cannot refresh while already showing the
  sleep image.
* The timer uses the tablet's local clock. Check with `date` over SSH: if it prints UTC
  instead of EEST/EET, change `OnCalendar` in `/etc/systemd/system/weather.timer` to
  the UTC equivalents and run `systemctl daemon-reload`.
* To go back to normal: `systemctl disable --now weather.timer`, then remove the
  `SleepScreenPath=` line from `/home/root/.config/remarkable/xochitl.conf`
  (with `systemctl stop xochitl` first, `systemctl start xochitl` after).

## Customising

Everything is in `render_weather.py`: `LAT/LON`, `SEA_LAT/SEA_LON`, `HOURS_AHEAD`,
`DAYS`, labels, fonts. Update times: the cron line + gate hours in
`.github/workflows/weather.yml`, and `OnCalendar` in `device/weather.timer`. Test locally on the Mac with `pip3 install pillow && python3 render_weather.py`
(writes `weather.png` next to the script) or `--mock` for fake data.
