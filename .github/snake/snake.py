"""Gold snake that eats the GitHub contribution graph.

Ten different routes; each run picks one at random, so the snake does not
run the same way every time.

Usage:  python snake.py <user> <out_dir> [route_name|random|all]
Needs GITHUB_TOKEN in the environment (GraphQL API).
"""
import json
import os
import random
import sys
import urllib.request

CELL, GAP = 11, 3
STEP = CELL + GAP
PAD_X, PAD_Y = 40, 46
PAD_R, PAD_B = 18, 34
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
STEP_TIME = 0.075          # seconds per cell
SNAKE_LEN = 6

THEMES = {
    "dark": {
        "empty": "#161b22",
        "levels": ["#161b22", "#3b3220", "#6b5626", "#a8853a", "#E2B857"],
        "head": "#F0D58C", "body": "#E2B857", "text": "#8b949e", "title": "#F0D58C",
    },
    "light": {
        "empty": "#ebedf0",
        "levels": ["#ebedf0", "#f3e3b5", "#e6c56f", "#c99a2e", "#9a7215"],
        "head": "#9a7215", "body": "#b8892a", "text": "#57606a", "title": "#9a7215",
    },
}
LEVEL = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2,
         "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}


# ---------------------------------------------------------------- data
def fetch_grid(user):
    query = """query($u:String!){user(login:$u){contributionsCollection{
      contributionCalendar{totalContributions weeks{contributionDays{weekday date contributionLevel}}}}}}"""
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": {"u": user}}).encode(),
        headers={"Authorization": "bearer " + os.environ["GITHUB_TOKEN"],
                 "Content-Type": "application/json"})
    data = json.load(urllib.request.urlopen(req))
    cal = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    weeks = cal["weeks"]
    grid, months, last = {}, [], None
    for x, w in enumerate(weeks):
        for d in w["contributionDays"]:
            grid[(x, d["weekday"])] = LEVEL[d["contributionLevel"]]
        m = int(w["contributionDays"][0]["date"][5:7])
        if m != last:
            months.append((x, MONTHS[m - 1]))
            last = m
    if len(months) > 1 and months[1][0] - months[0][0] < 3:
        months.pop(0)                    # avoid overlapping labels on the left edge
    return {"grid": grid, "months": months, "total": cal["totalContributions"]}, len(weeks)


# ---------------------------------------------------------------- routes
def link(points):
    """Connect waypoints with unit Manhattan steps."""
    out = [points[0]]
    for tx, ty in points[1:]:
        x, y = out[-1]
        horizontal_first = (len(out) % 2 == 0)
        while (x, y) != (tx, ty):
            if horizontal_first and x != tx or y == ty:
                x += 1 if tx > x else -1
            else:
                y += 1 if ty > y else -1
            out.append((x, y))
    return out


def rows(W, H, from_right=False, bottom_up=False):
    ys = range(H - 1, -1, -1) if bottom_up else range(H)
    pts = []
    for i, y in enumerate(ys):
        xs = list(range(W))
        if (i % 2 == 1) != from_right:
            xs.reverse()
        pts += [(x, y) for x in xs]
    return pts


def cols(W, H, from_right=False):
    xs = range(W - 1, -1, -1) if from_right else range(W)
    pts = []
    for i, x in enumerate(xs):
        ys = list(range(H)) if i % 2 == 0 else list(range(H - 1, -1, -1))
        pts += [(x, y) for y in ys]
    return pts


def spiral(W, H):
    l, t, r, b = 0, 0, W - 1, H - 1
    pts = []
    while l <= r and t <= b:
        pts += [(x, t) for x in range(l, r + 1)]
        pts += [(r, y) for y in range(t + 1, b + 1)]
        if t < b:
            pts += [(x, b) for x in range(r - 1, l - 1, -1)]
        if l < r:
            pts += [(l, y) for y in range(b - 1, t, -1)]
        l, t, r, b = l + 1, t + 1, r - 1, b - 1
    return pts


def diagonals(W, H):
    pts = []
    for s in range(W + H - 1):
        diag = [(x, s - x) for x in range(max(0, s - H + 1), min(W, s + 1))]
        pts += diag if s % 2 else diag[::-1]
    return pts


def waves(W, H):
    """Sweeps left->right in 2-row bands, like a sine wave."""
    pts = []
    for band in range(0, H, 2):
        row = [band, min(band + 1, H - 1)]
        xs = range(W) if (band // 2) % 2 == 0 else range(W - 1, -1, -1)
        for i, x in enumerate(xs):
            pts.append((x, row[i % 2]))
    return pts


def hunter(W, H, targets, rng, start):
    """Greedy: always runs to the nearest uneaten contribution."""
    left, pos, pts = set(targets), start, []
    while left:
        nxt = min(left, key=lambda c: (abs(c[0] - pos[0]) + abs(c[1] - pos[1]), rng.random()))
        pts.append(nxt)
        left.discard(nxt)
        pos = nxt
    return pts


def wanderer(W, H, targets, rng):
    """Visits contributions in random order with random detours."""
    order = list(targets)
    rng.shuffle(order)
    pts = []
    for c in order:
        if rng.random() < 0.6:
            pts.append((rng.randrange(W), rng.randrange(H)))
        pts.append(c)
    return pts


def build_routes(W, H, targets, seed):
    rng = random.Random(seed)
    return {
        "rows": rows(W, H),
        "rows-reverse": rows(W, H, from_right=True, bottom_up=True),
        "columns": cols(W, H),
        "columns-reverse": cols(W, H, from_right=True),
        "spiral-in": spiral(W, H),
        "spiral-out": spiral(W, H)[::-1],
        "diagonal": diagonals(W, H),
        "waves": waves(W, H),
        "hunter": hunter(W, H, targets, rng, (-1, rng.randrange(H))),
        "wanderer": wanderer(W, H, targets, rng),
    }


def full_path(route, W, H):
    first, last = route[0], route[-1]
    enter = (-3, first[1]) if first[0] < W / 2 else (W + 2, first[1])
    leave = (-3, last[1]) if last[0] < W / 2 else (W + 2, last[1])
    path = link([enter] + route + [leave])
    return path + [leave] * 12          # short pause off-screen before looping


# ---------------------------------------------------------------- svg
def render(info, W, route, theme):
    grid = info["grid"]
    th = THEMES[theme]
    path = full_path(route, W, 7)
    n = len(path)
    total = n * STEP_TIME
    px = lambda c: (PAD_X + c[0] * STEP, PAD_Y + c[1] * STEP)

    eaten = {}
    for i, c in enumerate(path):
        if grid.get(c, 0) > 0 and c not in eaten:
            eaten[c] = i

    css = [f"rect.c{{shape-rendering:geometricPrecision}}",
           f".s{{animation:mv {total:.2f}s linear infinite both}}"]
    kf = []
    for i, c in enumerate(path):
        x, y = px(c)
        kf.append(f"{i / (n - 1) * 100:.3f}%{{transform:translate({x}px,{y}px)}}")
    css.append("@keyframes mv{" + "".join(kf) + "}")

    cells = []
    for (x, y), lvl in sorted(grid.items()):
        X, Y = px((x, y))
        cls = ""
        if (x, y) in eaten:
            p = eaten[(x, y)] / (n - 1) * 100
            name = f"e{x}_{y}"
            css.append(f"@keyframes {name}{{0%,{p:.3f}%{{fill:{th['levels'][lvl]}}}"
                       f"{min(p + 0.05, 100):.3f}%,100%{{fill:{th['empty']}}}}}")
            cls = f' style="animation:{name} {total:.2f}s linear infinite"'
        cells.append(f'<rect class="c" x="{X}" y="{Y}" width="{CELL}" height="{CELL}" '
                     f'rx="2.5" fill="{th["levels"][lvl]}"{cls}/>')

    snake = []
    for k in range(SNAKE_LEN - 1, -1, -1):
        size = CELL - k * 0.9
        off = (CELL - size) / 2
        color = th["head"] if k == 0 else th["body"]
        op = 1 - k * 0.12
        snake.append(f'<rect class="s" x="{off:.2f}" y="{off:.2f}" width="{size:.2f}" '
                     f'height="{size:.2f}" rx="{size / 2.6:.2f}" fill="{color}" '
                     f'opacity="{op:.2f}" style="animation-delay:{k * STEP_TIME:.3f}s"/>')

    width = PAD_X + W * STEP - GAP + PAD_R
    grid_bottom = PAD_Y + 7 * STEP - GAP
    height = grid_bottom + PAD_B
    font = "font-family:'Segoe UI',-apple-system,Ubuntu,sans-serif"
    css.append(f"text{{{font};fill:{th['text']};font-size:11px}}"
               f".ttl{{font-size:14px;font-weight:600;fill:{th['title']}}}")
    labels = [f'<text class="ttl" x="{PAD_X}" y="18">{info["total"]} contributions in the last year</text>']
    labels += [f'<text x="{PAD_X + x * STEP}" y="{PAD_Y - 7}">{name}</text>' for x, name in info["months"]]
    labels += [f'<text x="{PAD_X - 8}" y="{PAD_Y + d * STEP + 9}" text-anchor="end">{n}</text>'
               for d, n in ((1, "Mon"), (3, "Wed"), (5, "Fri"))]
    lx = width - PAD_R - 5 * STEP - 30
    ly = grid_bottom + 14
    labels.append(f'<text x="{lx - 6}" y="{ly + 9}" text-anchor="end">Less</text>')
    labels += [f'<rect x="{lx + i * STEP}" y="{ly}" width="{CELL}" height="{CELL}" rx="2.5" fill="{c}"/>'
               for i, c in enumerate(th["levels"])]
    labels.append(f'<text x="{lx + 5 * STEP + 4}" y="{ly + 9}">More</text>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}">\n<style>{"".join(css)}</style>\n'
            + "\n".join(labels) + "\n" + "\n".join(cells) + "\n" + "\n".join(snake) + "\n</svg>\n")


def main():
    user, out = sys.argv[1], sys.argv[2]
    pick = sys.argv[3] if len(sys.argv) > 3 else "random"
    os.makedirs(out, exist_ok=True)
    info, W = fetch_grid(user)
    grid = info["grid"]
    targets = [c for c, v in grid.items() if v > 0] or [(W // 2, 3)]
    routes = build_routes(W, 7, targets, seed=random.random())

    if pick == "all":
        for name, r in routes.items():
            for theme in THEMES:
                with open(f"{out}/snake-{name}-{theme}.svg", "w", encoding="utf-8") as f:
                    f.write(render(info, W, r, theme))
        print("rendered", len(routes), "routes")
        return

    name = random.choice(list(routes)) if pick == "random" else pick
    for theme in THEMES:
        with open(f"{out}/snake-{theme}.svg", "w", encoding="utf-8") as f:
            f.write(render(info, W, routes[name], theme))
    print("route:", name)


if __name__ == "__main__":
    main()
