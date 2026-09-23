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

Models are pinned to the ones Windguru's free view shows — `gfs_seamless` for the
weather and `ncep_gfswave025` (NOAA WaveWatch III / GFS-Wave) for the swell — so the
numbers here line up with Windguru. `MODEL_WEATHER` / `MODEL_MARINE` in
`render_weather.py` change this. Open-Meteo's default, `best_match`, resolves to
ICON-EU (7 km, finer than GFS) plus Météo-France MFWAM at this spot; the models
genuinely disagree on swell, so switching changes both height and period.

## Part A — the renderer on GitHub (done)

Repo: <https://github.com/philippedagher/rm-weather> — public, so the tablet
downloads the PNG without needing any token.

The workflow renders on the schedule below, on every push to `main`, and on demand
from the **Actions** tab → *Render weather sleep screen* → **Run workflow**. Each
run force-pushes a single commit to the `output` branch, so history never grows.

Image URL (open it in a browser to check):
<https://raw.githubusercontent.com/philippedagher/rm-weather/output/weather.png>

Notes: GitHub cron runs in UTC and Lebanon changes between UTC+3 and UTC+2, so the
workflow is triggered at both possible UTC hours — eight times a day — and a first
step decides whether to actually render.

That step goes by **staleness, not clock hour**: it redraws only when the published
image is older than `MAX_AGE_MIN` (210 min). Because the four intended renders are at
least 4 h apart and the two UTC candidates for one Beirut slot are 1 h apart, any
threshold between those bounds yields four renders a day and collapses the DST pair.

It deliberately does not compare the current Beirut hour against 06/12/16/21, which is
what it used to do. GitHub delivers cron 1–2 h late often enough that the hour had
always moved on by the time a run started, so every scheduled run skipped itself and
the screen only ever updated when something was pushed.

GitHub also pauses schedules in repos with no commits for 60 days — any small commit
or pressing *Run workflow* re-enables it.

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

## Reaching the tablet

The tablet now holds a DHCP reservation in the router, so `~/.ssh/config` points
straight at that address:

```
Host remarkable
  HostName 192.168.86.33
  User root
  IdentityFile ~/.ssh/remarkable_ed25519
  IdentitiesOnly yes
```

Before that reservation its address moved (.37 -> .33) and ssh broke each time.
`mac/remarkable-resolve.sh` is the fallback for that: a ProxyCommand that finds
the tablet by MAC — reading the ARP cache, confirming the candidate actually
answers on port 22, and sweeping the local /24 if it is not cached yet. Copy it
to `~/.ssh/`, set `MAC` to your tablet's, and swap the `HostName` line for:

```
  ProxyCommand ~/.ssh/remarkable-resolve.sh %p
```

Drop `HostName` when using it: the ProxyCommand makes the connection, so ssh
records the host key under the name `remarkable` and it stays valid as the
address changes.

Note that a sleeping reMarkable leaves the network entirely — neither approach
can reach it until it is awake.

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
* **After a reMarkable OS update the screen stops refreshing.** An update replaces
  `/etc` and `/usr` wholesale, so `weather.service` and `weather.timer` disappear and
  nothing downloads any more; `/usr/share/remarkable/suspended.png` also reverts to the
  factory image. `/home/root` survives, so `sleep.png`, `update-weather.sh` and
  `xochitl.conf` (with its `SleepScreenPath`) are all still there — which is why the
  old picture keeps showing and the failure is easy to miss. Recover on the device,
  no Mac needed:
  ```
  ssh remarkable 'sh /home/root/weather/reinstall.sh'
  ```
  Check with `systemctl is-active weather.timer` — `inactive` or `not-found` means the
  update wiped it. (`install-on-device.sh` leaves that reinstall script, plus copies of
  the two unit files, under `/home/root/weather/` for exactly this.)
* OS 3.14–3.19 ignore `SleepScreenPath`; the script also overwrites
  `/usr/share/remarkable/suspended.png`, which works there, but that file is reset by
  every OS update — `reinstall.sh` restores it as part of its run.
* While asleep the tablet has no Wi-Fi and no timers run. If it was asleep at 06:20
  (say), the missed run is caught up as soon as you wake it (`Persistent=true`), so the
  *next* sleep shows the 06:00 forecast. It cannot refresh while already showing the
  sleep image.
* The timer uses the tablet's local clock, and this tablet runs in UTC (`date` over SSH
  prints UTC, not EEST/EET). `weather.timer` therefore lists UTC hours, with both the
  summer (UTC+3) and winter (UTC+2) candidates, so the DST switch needs no edit. If you
  ever set the tablet's timezone to Asia/Beirut, change `OnCalendar` back to
  `06,12,16,21:20:00` and run `systemctl daemon-reload`.
* To go back to normal: `systemctl disable --now weather.timer`, then remove the
  `SleepScreenPath=` line from `/home/root/.config/remarkable/xochitl.conf`
  (with `systemctl stop xochitl` first, `systemctl start xochitl` after).

## Customising

Everything is in `render_weather.py`: `LAT/LON`, `SEA_LAT/SEA_LON`, `HOURS_AHEAD`,
`DAYS`, labels, fonts. Update times: the cron line + gate hours in
`.github/workflows/weather.yml`, and `OnCalendar` in `device/weather.timer`.
Pushing any change under `.github/workflows/` needs a token with the `workflow`
scope (`gh auth refresh -s workflow` once), otherwise GitHub rejects the push.

Test locally on the Mac with `pip3 install pillow && python3 render_weather.py`
(writes `weather.png` next to the script) or `--mock` for fake data.
