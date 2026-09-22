#!/usr/bin/env python3
"""
Render an e-ink weather + sea dashboard for the reMarkable 2 sleep screen.

Hourly (next 24 h): rain probability, wind speed/gusts/direction,
                    swell height/period/direction.
Daily (10 days):    sky, temperatures, rain, wind (speed/gust/dir),
                    swell (height/period/dir).

Data: Open-Meteo forecast + marine APIs (free, no key).
Output: 1404x1872 greyscale PNG.

Usage:
    python3 render_weather.py                  # fetch live data -> weather.png
    python3 render_weather.py --out out.png
    python3 render_weather.py --mock           # fake data, for layout testing
"""
import argparse
import datetime as dt
import json
import math
import os
import sys
import urllib.request
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont

# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------
PLACE = "BATROUN"
LAT, LON = 34.2553, 35.6586            # Batroun town (weather)
SEA_LAT, SEA_LON = 34.243169, 35.658553  # swell point (Open-Meteo snaps to the nearest sea cell of its marine grid)
TZ = "Asia/Beirut"
HOURS_AHEAD = 24
DAYS = 10
W, H = 1404, 1872                      # reMarkable 2
MARGIN = 60

TZQ = TZ.replace("/", "%2F")

# Forecast models, pinned deliberately. Windguru's free view shows GFS for the
# weather columns and NOAA's WaveWatch III / GFS-Wave for the swell columns, so
# these keep our numbers in step with what it displays. Open-Meteo's default is
# "best_match", which resolves to ICON-EU + MFWAM at this location -- higher
# resolution, but different numbers, and it can change without notice as models
# are added. Pinning also means a model outage shows up as a failure here rather
# than as a silent switch to another model.
MODEL_WEATHER = "gfs_seamless"       # GFS, ~13 km  (Windguru "GFS 13")
MODEL_MARINE = "ncep_gfswave025"     # GFS-Wave 0.25 deg  (Windguru's wave data)

API_WEATHER = (
    "https://api.open-meteo.com/v1/forecast"
    f"?latitude={LAT}&longitude={LON}"
    "&hourly=precipitation_probability,wind_speed_10m,wind_gusts_10m,wind_direction_10m"
    "&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,"
    "precipitation_probability_max,wind_speed_10m_max,wind_gusts_10m_max,"
    "wind_direction_10m_dominant,sunrise,sunset"
    f"&timezone={TZQ}&forecast_days={DAYS}&wind_speed_unit=kmh"
    f"&models={MODEL_WEATHER}"
)
API_MARINE = (
    "https://marine-api.open-meteo.com/v1/marine"
    f"?latitude={SEA_LAT}&longitude={SEA_LON}"
    "&hourly=swell_wave_height,swell_wave_period,swell_wave_direction,wave_height"
    "&daily=swell_wave_height_max,swell_wave_period_max,swell_wave_direction_dominant,wave_height_max"
    f"&timezone={TZQ}&forecast_days={DAYS}"
    f"&models={MODEL_MARINE}"
)

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(HERE, "fonts")


def font(size, bold=False):
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    for p in (os.path.join(FONT_DIR, name),
              f"/usr/share/fonts/truetype/dejavu/{name}",
              f"/usr/share/fonts/dejavu/{name}"):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


WMO = {
    0: "Clear", 1: "Mostly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Rime fog",
    51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle",
    56: "Frz drizzle", 57: "Frz drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain",
    66: "Frz rain", 67: "Frz rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains",
    80: "Showers", 81: "Showers", 82: "Violent showers",
    85: "Snow showers", 86: "Snow showers",
    95: "Thunderstorm", 96: "T-storm, hail", 99: "T-storm, hail",
}
COMPASS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


def compass(deg):
    return COMPASS[int((deg + 22.5) // 45) % 8]


def v(lst, i, default=0.0):
    """Safe list access: Open-Meteo returns null for missing values."""
    try:
        x = lst[i]
        return default if x is None else x
    except (IndexError, TypeError):
        return default


# ----------------------------------------------------------------------------
# Data
# ----------------------------------------------------------------------------
def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "rm-weather/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch():
    wx = get_json(API_WEATHER)
    try:
        sea = get_json(API_MARINE)
    except Exception as e:        # marine API down -> still render the rest
        print("marine API failed:", e, file=sys.stderr)
        sea = {"hourly": {}, "daily": {}}
    return {"wx": wx, "sea": sea}


def mock():
    import random
    random.seed(7)
    now = dt.datetime.now(ZoneInfo(TZ)).replace(minute=0, second=0, microsecond=0)
    start = now.replace(hour=0)
    hours = [start + dt.timedelta(hours=i) for i in range(24 * DAYS)]
    days = [start + dt.timedelta(days=i) for i in range(DAYS)]
    ht = [h.strftime("%Y-%m-%dT%H:%M") for h in hours]
    dtm = [d.strftime("%Y-%m-%d") for d in days]
    wx = {"hourly": {
        "time": ht,
        "precipitation_probability": [int(50 + 45 * math.sin(h.hour / 5)) for h in hours],
        "wind_speed_10m": [12 + 14 * abs(math.sin(h.hour / 6)) for h in hours],
        "wind_gusts_10m": [22 + 20 * abs(math.sin(h.hour / 6)) for h in hours],
        "wind_direction_10m": [random.choice([200, 230, 250, 270, 300]) for h in hours],
    }, "daily": {
        "time": dtm,
        "weather_code": [random.choice([0, 1, 2, 3, 61, 63, 80, 95]) for _ in days],
        "temperature_2m_max": [random.uniform(26, 31) for _ in days],
        "temperature_2m_min": [random.uniform(19, 23) for _ in days],
        "precipitation_sum": [max(0, random.gauss(2, 6)) for _ in days],
        "precipitation_probability_max": [random.randint(0, 100) for _ in days],
        "wind_speed_10m_max": [random.uniform(10, 40) for _ in days],
        "wind_gusts_10m_max": [random.uniform(25, 70) for _ in days],
        "wind_direction_10m_dominant": [random.choice([200, 230, 250, 270, 300]) for _ in days],
        "sunrise": [d.strftime("%Y-%m-%dT06:24") for d in days],
        "sunset": [d.strftime("%Y-%m-%dT18:41") for d in days],
    }}
    sea = {"hourly": {
        "time": ht,
        "swell_wave_height": [0.6 + 0.5 * abs(math.sin(h.hour / 9)) for h in hours],
        "swell_wave_period": [5 + 4 * abs(math.sin(h.hour / 7)) for h in hours],
        "swell_wave_direction": [random.choice([250, 270, 290, 300]) for h in hours],
        "wave_height": [0.8 + 0.6 * abs(math.sin(h.hour / 9)) for h in hours],
    }, "daily": {
        "time": dtm,
        "swell_wave_height_max": [random.uniform(0.3, 2.2) for _ in days],
        "swell_wave_period_max": [random.uniform(4, 11) for _ in days],
        "swell_wave_direction_dominant": [random.choice([250, 270, 290, 300]) for _ in days],
        "wave_height_max": [random.uniform(0.5, 2.5) for _ in days],
    }}
    return {"wx": wx, "sea": sea}


# ----------------------------------------------------------------------------
# Drawing helpers
# ----------------------------------------------------------------------------
BLACK, DARK, MID, LIGHT, WHITE = 0, 70, 150, 215, 255


def text(d, xy, s, f, fill=BLACK, anchor="la"):
    d.text(xy, s, font=f, fill=fill, anchor=anchor)


def arrow(d, cx, cy, deg_from, r=16, fill=BLACK, width=4):
    """Arrow pointing where the wind/swell travels TO (meteorological deg = coming FROM)."""
    a = math.radians(deg_from + 180)
    tip = (cx + r * math.sin(a), cy - r * math.cos(a))
    tail = (cx - r * math.sin(a), cy + r * math.cos(a))
    d.line([tail, tip], fill=fill, width=width)
    for s in (+1, -1):
        b = a + s * math.radians(150)
        d.line([tip, (tip[0] + 0.55 * r * math.sin(b), tip[1] - 0.55 * r * math.cos(b))],
               fill=fill, width=width)


def hline(d, y, x0=MARGIN, x1=W - MARGIN, fill=BLACK, width=2):
    d.line([(x0, y), (x1, y)], fill=fill, width=width)


def dashed(d, pts, fill=DARK, width=3, segs=6):
    for k in range(len(pts) - 1):
        (ax, ay), (bx, by) = pts[k], pts[k + 1]
        for s in range(0, segs, 2):
            d.line([(ax + (bx - ax) * s / segs, ay + (by - ay) * s / segs),
                    (ax + (bx - ax) * (s + 1) / segs, ay + (by - ay) * (s + 1) / segs)],
                   fill=fill, width=width)


def chart_frame(d, x0, x1, top, ch, vmax, unit_fmt):
    bot = top + ch
    d.rectangle([x0, top, x1, bot], outline=MID, width=1)
    for frac in (1.0, 0.5, 0.0):
        yy = bot - frac * ch
        d.line([(x0, yy), (x1, yy)], fill=LIGHT, width=1)
        text(d, (x0 - 8, yy), unit_fmt(vmax * frac), font(20), fill=DARK, anchor="rm")
    return bot


# ----------------------------------------------------------------------------
# Panels
# ----------------------------------------------------------------------------
def draw_header(d, data, now):
    text(d, (MARGIN, 52), PLACE, font(64, True))
    text(d, (W - MARGIN, 62), now.strftime("%A %d %B"), font(34), anchor="ra")
    text(d, (W - MARGIN, 108), "updated " + now.strftime("%H:%M"), font(26), fill=DARK, anchor="ra")
    dly = data["wx"]["daily"]
    try:
        text(d, (MARGIN, 130), f"sunrise {dly['sunrise'][0][-5:]}   sunset {dly['sunset'][0][-5:]}",
             font(26), fill=DARK)
    except Exception:
        pass
    hline(d, 175, width=3)


def draw_hourly(d, data, now, top):
    h = data["wx"]["hourly"]
    s = data["sea"].get("hourly", {})
    times = [dt.datetime.fromisoformat(t).replace(tzinfo=now.tzinfo) for t in h["time"]]
    cur = now.replace(minute=0, second=0, microsecond=0)
    try:
        i0 = next(i for i, t in enumerate(times) if t >= cur)
    except StopIteration:
        i0 = 0
    idx = list(range(i0, min(i0 + HOURS_AHEAD, len(times))))
    n = len(idx)
    if n == 0:
        return top

    # marine series are aligned by timestamp (same timezone / hourly grid)
    sea_index = {t: k for k, t in enumerate(s.get("time", []))}
    sidx = [sea_index.get(h["time"][i]) for i in idx]

    prob = [v(h["precipitation_probability"], i) for i in idx]
    wind = [v(h["wind_speed_10m"], i) for i in idx]
    gust = [v(h["wind_gusts_10m"], i) for i in idx]
    wdir = [v(h["wind_direction_10m"], i) for i in idx]
    swh = [v(s.get("swell_wave_height", []), k) if k is not None else 0 for k in sidx]
    swp = [v(s.get("swell_wave_period", []), k) if k is not None else 0 for k in sidx]
    swd = [v(s.get("swell_wave_direction", []), k) if k is not None else 0 for k in sidx]
    have_sea = any(swh)

    text(d, (MARGIN, top), f"NEXT {n} HOURS", font(36, True))
    y = top + 56
    x0, x1 = MARGIN + 70, W - MARGIN - 10
    col = (x1 - x0) / n
    cx = [x0 + col * (k + 0.5) for k in range(n)]

    # hour labels
    f_hr = font(22, True)
    for k, i in enumerate(idx):
        lab = times[i].strftime("%a") if times[i].hour == 0 else times[i].strftime("%H")
        text(d, (cx[k], y), lab, f_hr, anchor="ma")
    text(d, (MARGIN, y), "h", f_hr, fill=DARK)
    y += 36

    # --- 1. rain probability (area + line, 0-100 %)
    text(d, (x0, y), "RAIN PROBABILITY %", font(20, True), fill=DARK)
    y += 28
    ch = 150
    bot = chart_frame(d, x0, x1, y, ch, 100, lambda x: f"{round(x)}%")
    pts = [(cx[k], bot - prob[k] / 100 * ch) for k in range(n)]
    d.polygon([(x0, bot)] + pts + [(x1, bot)], fill=LIGHT)
    d.line(pts, fill=BLACK, width=4)
    for k in range(0, n, 2):
        if prob[k] >= 15:
            text(d, (cx[k], pts[k][1] + 8), f"{round(prob[k])}", font(18), anchor="ma")
    y = bot + 16

    # --- 2. wind: speed (solid) + gusts (dashed) + direction arrows + speed numbers
    text(d, (x0, y), "WIND km/h  (solid = speed, dashed = gusts)", font(20, True), fill=DARK)
    y += 28
    ch = 170
    wmax = max(20.0, math.ceil(max(gust + wind) * 1.15 / 10) * 10)
    bot = chart_frame(d, x0, x1, y, ch, wmax, lambda x: f"{round(x)}")
    dashed(d, [(cx[k], bot - gust[k] / wmax * ch) for k in range(n)])
    wpts = [(cx[k], bot - wind[k] / wmax * ch) for k in range(n)]
    d.line(wpts, fill=BLACK, width=5)
    y = bot + 8
    for k in range(n):
        text(d, (cx[k], y), f"{round(wind[k])}", font(20), fill=DARK, anchor="ma")
        arrow(d, cx[k], y + 44, wdir[k], r=12, width=3)
    text(d, (MARGIN, y), "km/h", font(18), fill=DARK)
    text(d, (MARGIN, y + 34), "dir", font(18), fill=DARK)
    y += 70

    # --- 3. swell: height (bars) + period (numbers) + direction arrows
    ch = 170
    if have_sea:
        text(d, (x0, y), "SWELL  height m, period s, direction", font(20, True), fill=DARK)
        y += 28
        smax = max(1.0, math.ceil(max(swh) * 1.2 * 2) / 2)
        bot = chart_frame(d, x0, x1, y, ch, smax, lambda x: f"{x:.1f}")
        for k in range(n):
            bh = swh[k] / smax * ch
            if bh > 0:
                d.rectangle([cx[k] - col / 2 + 3, bot - bh, cx[k] + col / 2 - 3, bot], fill=DARK)
            if swh[k] >= 0.2:
                text(d, (cx[k], bot - bh - 4), f"{swh[k]:.1f}", font(16), anchor="md")
        y = bot + 8
        for k in range(n):
            text(d, (cx[k], y), f"{swp[k]:.0f}", font(20), fill=DARK, anchor="ma")
            arrow(d, cx[k], y + 44, swd[k], r=12, width=3)
        text(d, (MARGIN, y), "per. s", font(18), fill=DARK)
        text(d, (MARGIN, y + 34), "dir", font(18), fill=DARK)
        y += 70
    else:
        text(d, (x0, y), "swell data unavailable", font(24), fill=MID)
        y += 40

    hline(d, y, width=3)
    return y


def draw_daily(d, data, now, top):
    dl = data["wx"]["daily"]
    sd = data["sea"].get("daily", {})
    sea_index = {t: k for k, t in enumerate(sd.get("time", []))}
    n = min(DAYS, len(dl["time"]))
    text(d, (MARGIN, top), f"{n}-DAY OUTLOOK", font(36, True))
    y = top + 52

    c_day, c_sky, c_temp, c_rain, c_wind, c_swell = MARGIN, 215, 440, 585, 800, 1080
    f_h = font(21, True)
    for x, s_ in ((c_day, "day"), (c_sky, "sky"), (c_temp, "hi/lo °C"),
                  (c_rain, "rain mm (%)"), (c_wind, "wind km/h  gust  dir"),
                  (c_swell, "swell m  period  dir")):
        text(d, (x, y), s_, f_h, fill=DARK)
    y += 34
    hline(d, y, fill=MID, width=2)
    y += 6

    rowh = min(92, (H - MARGIN - y) // n)
    f_day, f_txt, f_sm = font(28, True), font(26), font(21)
    for i in range(n):
        ry = y + i * rowh
        cy = ry + rowh / 2
        date = dt.date.fromisoformat(dl["time"][i])
        label = "Today" if date == now.date() else date.strftime("%a %d")
        text(d, (c_day, cy), label, f_day, anchor="lm")
        text(d, (c_sky, cy), WMO.get(dl["weather_code"][i], "—"), f_sm, anchor="lm")
        text(d, (c_temp, cy), f"{round(v(dl['temperature_2m_max'], i))}/{round(v(dl['temperature_2m_min'], i))}",
             f_txt, anchor="lm")

        rs, rp = v(dl["precipitation_sum"], i), v(dl["precipitation_probability_max"], i)
        strong = rs >= 1
        text(d, (c_rain, cy), f"{rs:.1f} ({round(rp)}%)" if (rs >= 0.1 or rp >= 20) else "—",
             f_txt if strong else f_sm, fill=BLACK if strong else DARK, anchor="lm")
        bw = min(180, rs / 20 * 180)
        if bw > 0:
            d.rectangle([c_rain, cy + 20, c_rain + bw, cy + 27], fill=DARK)

        ws, wg, wd = v(dl["wind_speed_10m_max"], i), v(dl["wind_gusts_10m_max"], i), v(dl["wind_direction_10m_dominant"], i)
        strong = ws >= 25
        text(d, (c_wind, cy), f"{round(ws)}", f_txt if strong else f_sm, fill=BLACK if strong else DARK, anchor="lm")
        text(d, (c_wind + 70, cy), f"{round(wg)}", f_sm, fill=DARK, anchor="lm")
        arrow(d, c_wind + 150, cy, wd, r=14)
        text(d, (c_wind + 172, cy), compass(wd), f_sm, fill=DARK, anchor="lm")

        k = sea_index.get(dl["time"][i])
        if k is not None and sd.get("swell_wave_height_max"):
            sh, sp, sdir = (v(sd["swell_wave_height_max"], k), v(sd["swell_wave_period_max"], k),
                            v(sd["swell_wave_direction_dominant"], k))
            strong = sh >= 1.0
            text(d, (c_swell, cy), f"{sh:.1f}", f_txt if strong else f_sm, fill=BLACK if strong else DARK, anchor="lm")
            text(d, (c_swell + 70, cy), f"{sp:.0f}s", f_sm, fill=DARK, anchor="lm")
            arrow(d, c_swell + 150, cy, sdir, r=14)
            text(d, (c_swell + 172, cy), compass(sdir), f_sm, fill=DARK, anchor="lm")
        else:
            text(d, (c_swell, cy), "—", f_sm, fill=MID, anchor="lm")

        if i < n - 1:
            hline(d, ry + rowh - 1, fill=LIGHT, width=1)
    return y + n * rowh


# ----------------------------------------------------------------------------
def render(data, out):
    now = dt.datetime.now(ZoneInfo(TZ))
    img = Image.new("L", (W, H), WHITE)
    d = ImageDraw.Draw(img)
    draw_header(d, data, now)
    y = draw_hourly(d, data, now, 196)
    draw_daily(d, data, now, y + 20)
    img.save(out, "PNG", optimize=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "weather.png"))
    ap.add_argument("--mock", action="store_true")
    a = ap.parse_args()
    data = mock() if a.mock else fetch()
    if "hourly" not in data["wx"] or "daily" not in data["wx"]:
        print("unexpected API response:", json.dumps(data["wx"])[:300], file=sys.stderr)
        sys.exit(1)
    render(data, a.out)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
