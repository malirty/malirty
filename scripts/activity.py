#!/usr/bin/env python3
"""Render a 45-second, six-phase contribution calendar from real GitHub data.

The workflow uses GraphQL. --html-file accepts GitHub's public contribution
calendar for local visual verification when an API token is unavailable.
No SVG is written until the complete calendar has passed validation.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import random
import sys
import urllib.error
import urllib.request
from xml.sax.saxutils import escape


LEVELS = {
    "NONE": 0,
    "FIRST_QUARTILE": 1,
    "SECOND_QUARTILE": 2,
    "THIRD_QUARTILE": 3,
    "FOURTH_QUARTILE": 4,
}
THEMES = {
    "dark": {
        "empty": "#262a2f",
        "levels": ["#262a2f", "#4b5057", "#777e87", "#afb5bd", "#f1f3f5"],
        "text": "#a8adb4",
        "muted": "#737980",
        "rule": "#343940",
        "snake": "#eef0f3",
        "particle": "#dce0e4",
    },
    "light": {
        "empty": "#e9ebee",
        "levels": ["#e9ebee", "#c8ccd1", "#9ba1a8", "#656c75", "#252a30"],
        "text": "#3d434b",
        "muted": "#6f7780",
        "rule": "#d5d9dd",
        "snake": "#3c434c",
        "particle": "#626a73",
    },
}
CELL = 10
STEP = 13
LEFT = 47
TOP = 57
PERIOD = 45.0
MAX_SNAKE_SEGMENTS = 11
INITIAL_SNAKE_SEGMENTS = 3


def fetch_graphql(user: str) -> list[dict]:
    token = os.environ.get("GH_GRAPHQL_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GH_GRAPHQL_TOKEN or GITHUB_TOKEN is required for GraphQL")
    query = """query($login:String!){user(login:$login){contributionsCollection{
      contributionCalendar{totalContributions weeks{contributionDays{
        date weekday contributionCount contributionLevel}}}}}}"""
    body = json.dumps({"query": query, "variables": {"login": user}}).encode()
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
            "User-Agent": "malirty-profile-activity",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        # Never print a response body: it may contain request context.
        raise RuntimeError(f"GitHub GraphQL returned HTTP {exc.code}") from None
    except urllib.error.URLError as exc:
        raise RuntimeError(f"GitHub GraphQL network error: {exc.reason}") from None
    if payload.get("errors"):
        raise RuntimeError("GitHub GraphQL returned errors; calendar was not replaced")
    try:
        calendar = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]
        days = []
        for x, week in enumerate(calendar["weeks"]):
            for day in week["contributionDays"]:
                days.append({
                    "date": day["date"],
                    "x": x,
                    "y": int(day["weekday"]),
                    "count": int(day["contributionCount"]),
                    "level": LEVELS[day["contributionLevel"]],
                })
        if sum(day["count"] for day in days) != calendar["totalContributions"]:
            raise ValueError("contribution total disagrees with daily counts")
        return days
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError(f"Invalid GraphQL calendar: {exc}") from None


class CalendarHTML(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.days: list[dict] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "td":
            return
        a = dict(attrs)
        if "ContributionCalendar-day" not in (a.get("class") or ""):
            return
        if a.get("data-date") and a.get("data-level") is not None:
            self.days.append({"date": a["data-date"], "level": int(a["data-level"])})


def parse_public_html(html: str) -> list[dict]:
    parser = CalendarHTML()
    parser.feed(html)
    if not parser.days:
        raise RuntimeError("No GitHub contribution cells found in HTML")
    first = min(dt.date.fromisoformat(d["date"]) for d in parser.days)
    first_sunday = first - dt.timedelta(days=(first.weekday() + 1) % 7)
    for day in parser.days:
        date = dt.date.fromisoformat(day["date"])
        day["x"] = (date - first_sunday).days // 7
        day["y"] = (date.weekday() + 1) % 7
        day["count"] = 0 if day["level"] == 0 else 1
    return parser.days


def load_public_html(path: Path) -> list[dict]:
    return parse_public_html(path.read_text(encoding="utf-8"))


def fetch_public_html(user: str) -> list[dict]:
    request = urllib.request.Request(
        f"https://github.com/users/{user}/contributions",
        headers={"User-Agent": "malirty-profile-activity"},
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            html = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"GitHub public calendar returned HTTP {exc.code}") from None
    except urllib.error.URLError as exc:
        raise RuntimeError(f"GitHub public calendar network error: {exc.reason}") from None
    return parse_public_html(html)


def validate(days: list[dict]) -> list[dict]:
    if not 350 <= len(days) <= 371:
        raise RuntimeError(f"Expected a full-year calendar, got {len(days)} days")
    result = sorted(days, key=lambda d: d["date"])
    dates = [dt.date.fromisoformat(d["date"]) for d in result]
    if len(set(dates)) != len(dates):
        raise RuntimeError("Duplicate contribution dates")
    if any((b - a).days != 1 for a, b in zip(dates, dates[1:])):
        raise RuntimeError("Contribution calendar has missing dates")
    if dates[-1] < dt.date.today() - dt.timedelta(days=3):
        raise RuntimeError("Contribution calendar is stale")
    if any(d["level"] not in range(5) or d["count"] < 0 or
           d["y"] not in range(7) or d["x"] < 0 for d in result):
        raise RuntimeError("Invalid contribution cell")
    if any((d["count"] == 0) != (d["level"] == 0) for d in result):
        raise RuntimeError("Contribution counts and intensity levels disagree")
    return result


def route(targets: set[tuple[int, int]], width: int) -> list[tuple[int, int]]:
    """Nearest real targets, linked by adjacent Manhattan grid steps."""
    if not targets:
        return [(x, 3) for x in range(2, width + 2)]
    remaining = set(targets)
    start = min(remaining, key=lambda p: (p[0], p[1]))
    # The head starts at column 2, leaving two visible squares behind it.
    pos = (2, start[1])
    path = [pos]
    remaining.discard(pos)
    while remaining:
        target = min(remaining, key=lambda p: (abs(p[0] - pos[0]) + abs(p[1] - pos[1]), p[0], p[1]))
        # Alternating axis order keeps long straight traversals from dominating.
        horizontal_first = len(path) % 2 == 0
        while pos != target:
            x, y = pos
            if (horizontal_first and x != target[0]) or y == target[1]:
                x += 1 if target[0] > x else -1
            else:
                y += 1 if target[1] > y else -1
            pos = (x, y)
            path.append(pos)
            remaining.discard(pos)
    while pos[0] < width + 1:
        pos = (pos[0] + 1, pos[1])
        path.append(pos)
    return path


def pct(seconds: float) -> str:
    return f"{seconds / PERIOD * 100:.4f}%"


def keyframes(name: str, frames: list[tuple[float, str]]) -> str:
    # Distinct chronological times are important for a continuous 45 s loop.
    frames.sort(key=lambda item: item[0])
    if any(b[0] <= a[0] for a, b in zip(frames, frames[1:])):
        raise ValueError(f"Non-increasing keyframes: {name}")
    return "@keyframes " + name + "{" + "".join(
        pct(t) + "{" + style + "}" for t, style in frames
    ) + "}"


def transform(dx: float = 0, dy: float = 0, scale: float = 1) -> str:
    return f"transform:translate({dx:.2f}px,{dy:.2f}px) scale({scale:.3f})"


def render(days: list[dict], theme: str) -> str:
    th = THEMES[theme]
    width = max(d["x"] for d in days) + 1
    filled = [d for d in days if d["level"]]
    filled_index = {(d["x"], d["y"]): i for i, d in enumerate(filled)}
    targets = {(d["x"], d["y"]) for d in filled}
    path = route(targets, width)
    contact = {p: i for i, p in enumerate(path) if p in targets}
    # Keep the first contact, including cells crossed on the way to a target.
    for i, p in enumerate(path):
        if p in targets:
            contact[p] = min(i, contact[p])
    seed_material = ";".join(f"{d['date']}:{d['level']}:{d['count']}" for d in days)
    rng = random.Random(int(hashlib.sha256(seed_material.encode()).hexdigest()[:16], 16))
    slots = [(d["x"], d["y"]) for d in filled]
    shuffled = slots[:]
    rng.shuffle(shuffled)
    if len(slots) > 1 and shuffled == slots:
        shuffled = shuffled[1:] + shuffled[:1]

    css = [
        "text{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}",
        ".mono{font-family:ui-monospace,SFMono-Regular,Consolas,monospace}",
        ".snake-window{animation:snake-visible 45s linear infinite}",
        keyframes("snake-visible", [(0, "opacity:1"), (14.8, "opacity:1"),
                                    (15, "opacity:0"), (45, "opacity:0")]),
    ]
    body = []
    for day in days:
        x, y, level = day["x"], day["y"], day["level"]
        cx, cy = LEFT + x * STEP + CELL / 2, TOP + y * STEP + CELL / 2
        color = th["levels"][level]
        if level == 0:
            body.append(f'<rect x="{cx-5:g}" y="{cy-5:g}" width="10" height="10" rx="2.4" fill="{color}"/>')
            continue
        index = filled_index[(x, y)]
        eat = 14.45 * contact[(x, y)] / max(1, len(path) - 1)
        restore_start = 15.05 + rng.uniform(0, 4.45)
        restore_end = min(20.95, restore_start + rng.uniform(.35, 1.20))
        phase = rng.uniform(0, 1.0)
        css.append(f".c{index}{{animation:v{index} 45s linear infinite,m{index} 45s ease-in-out infinite}}")
        css.append(keyframes(f"v{index}", [
            (0, "opacity:1"), (max(.001, eat - .015), "opacity:1"),
            (eat + .10, "opacity:0"), (15, "opacity:0"),
            (restore_start, "opacity:0"), (restore_end, "opacity:1"),
            (27, "opacity:1"), (27.35, "opacity:0"),
            (32.65, "opacity:0"), (33, "opacity:1"),
            (39, "opacity:1"), (40 + phase, "opacity:.77"),
            (42 + phase, "opacity:1"), (43.5 + phase / 2, "opacity:.90"),
            (45, "opacity:1"),
        ]))
        delay = rng.uniform(.05, .70)
        fall = rng.uniform(.85, 1.45)
        # Land below the bottom row while retaining room inside the viewBox.
        drop = (6 - y) * STEP + rng.uniform(15, 22)
        impact = 21 + delay + fall
        rebound = impact + rng.uniform(.19, .31)
        settle = rebound + rng.uniform(.30, .45)
        return_start = 24.10 + rng.uniform(0, .45)
        return_end = 26.62 + rng.uniform(0, .25)
        rebound_y = drop - min(10, drop * .22)
        other_x, other_y = shuffled[index]
        dx, dy = (other_x - x) * STEP, (other_y - y) * STEP
        shuffle_delay = rng.uniform(0, .75)
        css.append(keyframes(f"m{index}", [
            (0, transform()),
            (21 + delay, transform() + ";animation-timing-function:cubic-bezier(.55,.02,.95,.55)"),
            (impact, transform(0, drop, .94) + ";animation-timing-function:cubic-bezier(.08,.82,.24,1)"),
            (rebound, transform(0, rebound_y, 1.025) + ";animation-timing-function:cubic-bezier(.5,0,.9,.5)"),
            (settle, transform(0, drop - min(2, drop * .1)) + ";animation-timing-function:ease-in"),
            # One continuous ascent: zero velocity at both ends, fastest near the middle.
            (return_start, transform(0, drop) + ";animation-timing-function:cubic-bezier(.65,0,.35,1)"),
            (return_end, transform()), (27, transform()),
            (33, transform()), (33 + shuffle_delay, transform()),
            (35.7 + shuffle_delay / 3, transform(dx, dy, .93)),
            (36.8, transform(dx, dy, .93)), (39, transform()),
            (40 + phase, transform(scale=1.09)),
            (42 + phase, transform()),
            (43.5 + phase / 2, transform(scale=1.04)),
            (45, transform()),
        ]))
        body.append(
            f'<g transform="translate({cx:g} {cy:g})"><g class="c{index}">'
            f'<rect x="-5" y="-5" width="10" height="10" rx="2.4" fill="{color}"/>'
            '</g></g>'
        )
        for dot in range(3):
            angle_x = rng.uniform(-1, 1)
            angle_y = rng.uniform(-1, 1)
            distance = rng.uniform(11, 27)
            px, py = angle_x * distance, angle_y * distance
            name = f"p{index}_{dot}"
            css.append(f".{name}{{animation:{name} 45s ease-in-out infinite}}")
            css.append(keyframes(name, [
                (0, "opacity:0;" + transform()),
                (27, "opacity:0;" + transform()),
                (27.4, "opacity:1;" + transform()),
                (29.5 + rng.uniform(-.4, .4), "opacity:.75;" + transform(px, py, .75)),
                (31.2, "opacity:.55;" + transform(px * .75, py * .75, .65)),
                (32.85, "opacity:.85;" + transform()),
                (33, "opacity:0;" + transform()),
                (45, "opacity:0;" + transform()),
            ]))
            ox, oy = rng.uniform(-2, 2), rng.uniform(-2, 2)
            body.append(
                f'<g transform="translate({cx:g} {cy:g})"><circle class="{name}" '
                f'cx="{ox:.2f}" cy="{oy:.2f}" r="1.35" fill="{th["particle"]}" opacity="0"/></g>'
            )

    # Three squares are visible from the first frame; later contributions
    # unlock more of the translucent tail.
    contact_steps = sorted(contact.values())
    snake_count = min(MAX_SNAKE_SEGMENTS, len(contact_steps) + INITIAL_SNAKE_SEGMENTS)
    first_y = path[0][1]
    trail = [(-1, first_y), (0, first_y), (1, first_y)] + path
    snake_parts = []
    for segment in range(snake_count - 1, -1, -1):
        name = f"snake-move{segment}"
        css.append(f".{name}{{animation:{name} 45s linear infinite}}")
        frames = []
        for i in range(len(path)):
            x, y = trail[max(0, INITIAL_SNAKE_SEGMENTS + i - segment)]
            t = 14.45 * i / max(1, len(path) - 1)
            frames.append((t, transform(LEFT + x * STEP + 5, TOP + y * STEP + 5)))
        frames.append((45, frames[-1][1]))
        css.append(keyframes(name, frames))
        grow = f"snake-grow{segment}"
        if segment == 0:
            opacity = 1.0
        elif segment == 1:
            opacity = .55
        else:
            opacity = max(.08, .30 * .83 ** (segment - 2))
        if segment < INITIAL_SNAKE_SEGMENTS:
            growth_frames = [(0, f"opacity:{opacity:.3f}"),
                             (14.8, f"opacity:{opacity:.3f}"),
                             (15, "opacity:0"), (45, "opacity:0")]
        else:
            unlock = 14.45 * contact_steps[segment - INITIAL_SNAKE_SEGMENTS] / max(1, len(path) - 1)
            unlock = max(.01, unlock)
            growth_frames = [(0, "opacity:0"), (unlock, "opacity:0"),
                             (min(unlock + .18, 14.75), f"opacity:{opacity:.3f}"),
                             (14.8, f"opacity:{opacity:.3f}"),
                             (15, "opacity:0"), (45, "opacity:0")]
        css.append(keyframes(grow, growth_frames))
        animation = f"{grow} 45s ease-out infinite"
        if segment == 0:
            css.append(keyframes("snake-head-size", [
                (0, "transform:scale(1)"), (14.45, "transform:scale(1.16)"),
                (15, "transform:scale(1)"), (45, "transform:scale(1)"),
            ]))
            animation += ",snake-head-size 45s ease-in-out infinite"
        css.append(f".snake-piece{segment}{{animation:{animation}}}")
        size = max(2.8, 10 - .72 * segment)
        offset = -size / 2
        snake_parts.append(
            f'<g class="{name}"><rect class="snake-piece{segment}" '
            f'x="{offset:.2f}" y="{offset:.2f}" width="{size:.2f}" height="{size:.2f}" '
            f'rx="{min(1.8, size * .18):.2f}" fill="{th["snake"]}" opacity="0"/></g>'
        )
    snake = "".join(snake_parts)

    months = []
    previous_month = None
    previous_x = -3
    for day in days:
        date = dt.date.fromisoformat(day["date"])
        month = (date.year, date.month)
        if month != previous_month:
            if day["x"] - previous_x >= 3:
                months.append((day["x"], date.strftime("%b").upper()))
                previous_x = day["x"]
            previous_month = month
    labels = "".join(
        f'<text x="{LEFT+x*STEP}" y="49" font-size="9" letter-spacing="1.3" fill="{th["muted"]}">{escape(month)}</text>'
        for x, month in months
    )
    labels += "".join(
        f'<text x="37" y="{TOP+y*STEP+8}" text-anchor="end" font-size="9" fill="{th["muted"]}">{label}</text>'
        for y, label in ((1, "M"), (3, "W"), (5, "F"))
    )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="171" '
        'viewBox="0 0 800 171" role="img" aria-labelledby="title desc">'
        '<title id="title">GitHub contribution activity</title>'
        f'<desc id="desc">Real contribution calendar for malirty, {escape(days[0]["date"])} to '
        f'{escape(days[-1]["date"])}. A 45-second animation moves through snake, random restore, '
        'gravity, particles, shuffle, and pulse phases.</desc>'
        '<style>' + "".join(css) + '</style>'
        f'<text x="47" y="21" font-size="13" font-weight="650" letter-spacing="1.1" fill="{th["text"]}">CONTRIBUTION ACTIVITY</text>'
        f'<text class="mono" x="755" y="21" text-anchor="end" font-size="10" letter-spacing="1.1" fill="{th["muted"]}">LAST 12 MONTHS</text>'
        f'<path d="M47 29H755" stroke="{th["rule"]}" stroke-width="1"/>'
        + labels + "".join(body)
        + '<g class="snake-window" opacity="0">' + snake + '</g>'
        + '</svg>\n'
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", default="malirty")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--html-file", type=Path, help="local GitHub public-calendar HTML for visual QA")
    args = parser.parse_args()
    try:
        if args.html_file:
            days = validate(load_public_html(args.html_file))
        else:
            try:
                days = validate(fetch_graphql(args.user))
                print("Source: GitHub GraphQL contribution calendar")
            except RuntimeError as exc:
                # GitHub's own public profile calendar needs no user token.
                # The fallback is still validated before any file is replaced.
                print(f"GraphQL unavailable ({exc}); trying GitHub public calendar", file=sys.stderr)
                days = validate(fetch_public_html(args.user))
                print("Source: GitHub public contribution calendar")
        graphics = {theme: render(days, theme) for theme in THEMES}
        # Parsing before writing catches invalid XML and keeps prior files intact.
        import xml.etree.ElementTree as ET
        for svg in graphics.values():
            ET.fromstring(svg)
        args.output.mkdir(parents=True, exist_ok=True)
        for theme, svg in graphics.items():
            target = args.output / f"activity-{theme}.svg"
            temporary = target.with_suffix(".svg.tmp")
            temporary.write_text(svg, encoding="utf-8")
            temporary.replace(target)
        print(f"Rendered {len(days)} real days, {sum(d['level'] > 0 for d in days)} active cells")
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Activity generation stopped: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
