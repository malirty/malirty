#!/usr/bin/env python3
"""Build the terminal and monochrome technology artwork.

Logo contours are from Simple Icons (CC0), stored locally in scripts/icons.
The published SVG has no remote assets, scripts, fonts, or color logos.
"""

from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
ICON_DIR = ROOT / "scripts" / "icons"
PERIOD = 14.0


def percent(time: float) -> str:
    return f"{time / PERIOD * 100:.4f}%"


def keyframes(name: str, frames: list[tuple[float, str]]) -> str:
    return "@keyframes " + name + "{" + "".join(
        percent(time) + "{" + style + "}" for time, style in frames
    ) + "}"


def build_stack(mobile: bool = False) -> str:
    items = [
        ("python", "Python"), ("javascript", "JavaScript"),
        ("html5", "HTML"), ("css3", "CSS"), ("nodedotjs", "Node.js"),
        ("electron", "Electron"), ("swift", "Swift"),
        ("git", "Git"), ("github", "GitHub"),
        ("visualstudiocode", "VS Code"),
    ]
    icons = []
    offsets = (0, -2.7, -4.5, -1.1, -3.6, -5.2, -.8, -4.1, -2.0, -5.8)
    for index, (slug, label) in enumerate(items):
        root = ET.parse(ICON_DIR / (slug + ".svg")).getroot()
        path = root.find("{http://www.w3.org/2000/svg}path")
        if path is None or not path.get("d"):
            raise ValueError(f"Missing icon contour: {slug}")
        data = escape(path.attrib["d"], {'"': "&quot;"})
        x = (105 + (index % 2) * 150) if mobile else (100 + (index % 5) * 150)
        y = (80 + (index // 2) * 80) if mobile else (82 + (index // 5) * 91)
        icons.append(
            f'<g transform="translate({x-17} {y-17}) scale(1.416667)">'
            f'<path class="logo" style="animation-delay:{offsets[index]:.1f}s" d="{data}"/></g>'
            f'<text class="label" x="{x}" y="{y+42}" text-anchor="middle">{escape(label)}</text>'
        )
    canvas_width = 360 if mobile else 800
    canvas_height = 452 if mobile else 236
    rule = '<path class="rule" d="M35 38H325" stroke-width="1"/>' if mobile else \
        '<path class="rule" d="M60 38H740 M60 144H740" stroke-width="1"/>'
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_width}" height="{canvas_height}" '
        f'viewBox="0 0 {canvas_width} {canvas_height}" role="img" aria-labelledby="title desc">'
        '<title id="title">Tech stack</title>'
        '<desc id="desc">Python, JavaScript, HTML, CSS, Node.js, Electron, Swift, Git, GitHub, and VS Code.</desc>'
        '<style>'
        '.heading{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;font-size:13px;font-weight:650;letter-spacing:1.2px;fill:#a9aeb5}'
        '.label{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;font-size:12px;font-weight:500;fill:#a9aeb5}'
        '.logo{fill:#d6d9de;animation:icon-light 6.4s ease-in-out infinite}.rule{stroke:#353a40}'
        '@keyframes icon-light{0%,68%,100%{opacity:.78}80%{opacity:1}89%{opacity:.78}}'
        '@media(prefers-color-scheme:light){.heading,.label{fill:#505861}.logo{fill:#444c55}.rule{stroke:#dadde1}}'
        '@media(prefers-reduced-motion:reduce){.logo{animation:none}}'
        '</style>'
        f'<text class="heading" x="{canvas_width//2}" y="25" text-anchor="middle">TECH STACK</text>'
        + rule
        + "".join(icons) + '</svg>\n'
    )


def build_terminal(mobile: bool = False) -> str:
    canvas_width = 360 if mobile else 800
    text_x = 59 if mobile else 106
    number_x = 20 if mobile else 47
    line_x = 44 if mobile else 88
    right_x = canvas_width - (19 if mobile else 29)
    char_width = 8.45 if mobile else 9.15
    duration = f"{PERIOD:g}s"
    css = [
        "text{font-family:ui-monospace,SFMono-Regular,Consolas,'Liberation Mono',monospace}",
        f'.bar{{font-size:{11 if mobile else 13}px;fill:#a9adb2}}.num{{font-size:11px;letter-spacing:1px;fill:#777d84}}',
        f'.command{{font-size:{14 if mobile else 15}px;fill:#f1f2f3}}.answer{{font-size:{12.5 if mobile else 14}px;fill:#aeb3b9}}',
        f".screen{{animation:screen {duration} linear infinite}}",
        keyframes("screen", [(0, "opacity:0"), (.12, "opacity:1"),
                              (12.6, "opacity:1"), (13.55, "opacity:0"),
                              (PERIOD, "opacity:0")]),
        ".blink{animation:blink .52s steps(1,end) infinite}",
        "@keyframes blink{0%,49%{opacity:1}50%,99%{opacity:0}100%{opacity:1}}",
        ".status{animation:status 2.2s ease-in-out infinite}",
        "@keyframes status{0%,100%{opacity:.55}50%{opacity:1}}",
        "@media(prefers-reduced-motion:reduce){*{animation:none!important}}",
    ]

    def reveal(name: str, start: float) -> None:
        css.append(f".{name}{{animation:{name} {duration} ease-out infinite}}")
        hidden = "opacity:0;transform:translateY(3px)"
        shown = "opacity:1;transform:translateY(0px)"
        css.append(keyframes(name, [(0, hidden), (start, hidden),
                                    (start + .15, shown),
                                    (12.6, shown), (13.55, hidden),
                                    (PERIOD, hidden)]))

    def phase(name: str, start: float, end: float) -> None:
        css.append(f".{name}{{animation:{name} {duration} linear infinite}}")
        css.append(keyframes(name, [(0, "opacity:0"), (start-.02, "opacity:0"),
                                    (start, "opacity:1"), (end-.02, "opacity:1"),
                                    (end, "opacity:0"), (PERIOD, "opacity:0")]))

    blocks = [
        ("01", "❯ uptime", 102, .22, .68),
        ("02", "❯ philosophy", 188, 1.22, 1.88),
        ("03", "❯ skills", 275, 2.55, 3.02),
        ("04", "❯ mindless", 405, 4.45, 5.12),
    ]
    clips = []
    parts = []
    for i, (number, command, baseline, start, end) in enumerate(blocks):
        length = len(command)
        full_width = length * char_width + 4
        name = f"type{i}"
        css.append(f".{name}{{animation:{name} {duration} steps({length},end) infinite}}")
        css.append(keyframes(name, [(0, "width:0"), (start, "width:0"),
                                    (end, f"width:{full_width:.2f}px"),
                                    (PERIOD, f"width:{full_width:.2f}px")]))
        cursor_name = f"typingCursor{i}"
        css.append(f".{cursor_name}{{animation:{cursor_name} {duration} steps({length},end) infinite}}")
        css.append(keyframes(cursor_name, [
            (0, "opacity:0;transform:translateX(0px)"),
            (start-.01, "opacity:0;transform:translateX(0px)"),
            (start, "opacity:1;transform:translateX(0px)"),
            (end, f"opacity:1;transform:translateX({full_width:.2f}px)"),
            (end+.08, f"opacity:0;transform:translateX({full_width:.2f}px)"),
            (PERIOD, "opacity:0;transform:translateX(0px)"),
        ]))
        rail_name = f"rail{i}"
        css.append(f".{rail_name}{{animation:{rail_name} {duration} ease-in-out infinite}}")
        css.append(keyframes(rail_name, [
            (0, "opacity:0"), (start, "opacity:0"),
            (start+.16, "opacity:.9"), (end+.25, "opacity:.22"),
            (12.6, "opacity:.22"), (13.55, "opacity:0"),
            (PERIOD, "opacity:0"),
        ]))
        clips.append(
            f'<clipPath id="clip{i}"><rect class="{name}" x="{text_x}" y="{baseline-19}" '
            f'width="{full_width:.2f}" height="26"/></clipPath>'
        )
        reveal(f"block{i}", start)
        line_top = baseline - 28
        line_bottom = [133, 220, 352, 451][i]
        parts.append(
            f'<g class="block{i}"><text class="num" x="{number_x}" y="{baseline-2}">{number}</text>'
            f'<path d="M{line_x} {line_top}V{line_bottom}" stroke="#343a40" stroke-width="1"/>'
            f'<path class="{rail_name}" d="M{line_x} {line_top}V{line_bottom}" '
            'stroke="#bfc4ca" stroke-width="1.5" opacity="0"/>'
            f'<text class="command" x="{text_x}" y="{baseline}" clip-path="url(#clip{i})">'
            f'{escape(command)}</text></g>'
        )
        parts.append(
            f'<g class="{cursor_name}" opacity="0"><rect class="blink" '
            f'x="{text_x}" y="{baseline-15}" width="6" height="16" rx="1" fill="#d8dbe0"/></g>'
        )
    reveal("answer0", .82)
    reveal("answer1", 2.05)
    for name, start in (("skill0", 3.18), ("skill1", 3.34), ("skill2", 3.50)):
        reveal(name, start)
    parts.extend([
        f'<text class="answer answer0" x="{text_x}" y="128">Developing since 2019.</text>',
        f'<text class="answer answer1" x="{text_x}" y="214">Nothing is ever truly finished.</text>',
        f'<text class="answer skill0" x="{text_x}" y="301">Python · JavaScript · Swift</text>',
        f'<text class="answer skill1" x="{text_x}" y="324">HTML · CSS · Node.js · Electron</text>',
        f'<text class="answer skill2" x="{text_x}" y="347">UI/UX · AI · Automation</text>',
    ])

    for name, content, start, end in (
        ("process1", "Processing.", 5.50, 5.97),
        ("process2", "Processing..", 5.97, 6.40),
        ("process3", "Processing…", 6.40, 6.88),
    ):
        phase(name, start, end)
        parts.append(f'<text class="answer {name}" x="{text_x}" y="437" opacity="0">{escape(content)}</text>')
    phase("generate", 6.88, 9.35)
    css.append(f".erase{{animation:erase {duration} steps(20,end) infinite}}")
    css.append(keyframes("erase", [(0, "width:220px"), (8.15, "width:220px"),
                                  (9.24, "width:0"), (PERIOD, "width:0")]))
    clips.append(f'<clipPath id="erase"><rect class="erase" x="{text_x}" y="418" width="220" height="25"/></clipPath>')
    parts.append(f'<text class="answer generate" x="{text_x}" y="437" opacity="0" '
                 'clip-path="url(#erase)">Generating response…</text>')
    reveal("final", 9.62)
    parts.append(f'<g class="final"><text class="answer" x="{text_x}" y="437">null</text>'
                 f'<rect class="blink" x="{text_x+39}" y="424" width="7" height="15" rx="1" fill="#d8dbe0"/>'
                 '</g>')

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_width}" height="510" '
        f'viewBox="0 0 {canvas_width} 510" role="img" aria-labelledby="title desc">'
        '<title id="title">malirty terminal</title>'
        '<desc id="desc">Four typed commands: uptime, philosophy, skills, and mindless. '
        'The last response processes, pauses, erases, and settles on null.</desc>'
        '<defs>' + "".join(clips) + '</defs><style>' + "".join(css) + '</style>'
        f'<rect x="1" y="1" width="{canvas_width-2}" height="508" rx="15" fill="#0c0c0c" '
        'stroke="#303030" stroke-width="2"/>'
        f'<path d="M15 1H{canvas_width-15}Q{canvas_width-1} 1 {canvas_width-1} 15V45H1V15Q1 1 15 1Z" fill="#151515"/>'
        f'<path d="M1 470H{canvas_width-1}V495Q{canvas_width-1} 509 {canvas_width-15} 509H15Q1 509 1 495Z" fill="#151515"/>'
        f'<path d="M1 45H{canvas_width-1}M1 470H{canvas_width-1}" stroke="#303030"/>'
        f'<text class="bar" x="{19 if mobile else 27}" y="29">⌘ malirty / ~</text>'
        f'<text class="bar" x="{right_x}" y="29" text-anchor="end">zsh ◫</text>'
        f'<circle class="status" cx="{20 if mobile else 28}" cy="490" r="3.4" fill="#c8cbd0"/>'
        f'<text class="bar" x="{34 if mobile else 42}" y="495">zsh</text>'
        f'<text class="bar" x="{right_x}" y="495" text-anchor="end">UTF-8 / ~</text>'
        '<g class="screen">' + "".join(parts) + '</g>'
        '</svg>\n'
    )


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    for filename, svg in (("tech-stack.svg", build_stack()),
                          ("tech-stack-mobile.svg", build_stack(mobile=True)),
                          ("terminal-mono.svg", build_terminal()),
                          ("terminal-mobile.svg", build_terminal(mobile=True))):
        ET.fromstring(svg)
        (ASSETS / filename).write_text(svg, encoding="utf-8")
        print(f"Wrote {filename}")


if __name__ == "__main__":
    main()
