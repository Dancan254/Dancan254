#!/usr/bin/env python3
"""Render the contribution calendar into assets/graph.svg in brand colours.

Standard library only. Replaces github-readme-activity-graph.vercel.app, which
started returning 402 and left a broken image on the profile.
"""

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

GRAPH = Path(__file__).resolve().parent.parent / "assets" / "graph.svg"

GRAPHQL = "https://api.github.com/graphql"
USER = os.environ.get("PROFILE_USER", "Dancan254")

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""

BG = "#12121f"
BORDER = "#2e2e4a"
TITLE = "#FFFFFF"
MUTED = "#6B7A99"
# Empty day, then four buckets ramping to the brand accent.
LEVELS = ["#1a1a2e", "#4a1330", "#90184a", "#d01860", "#f0196a"]

CELL = 11
PITCH = 14
GRID_X = 52
GRID_Y = 72
WIDTH = 820
HEIGHT = 220

SANS = "'Bricolage Grotesque', 'Segoe UI', system-ui, -apple-system, Helvetica, Arial, sans-serif"
MONO = "'JetBrains Mono', Menlo, 'DejaVu Sans Mono', Consolas, monospace"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def token():
    for name in ("PROFILE_TOKEN", "GITHUB_TOKEN"):
        value = os.environ.get(name)
        if value:
            return value
    raise SystemExit("no PROFILE_TOKEN or GITHUB_TOKEN in the environment")


def fetch_calendar():
    payload = json.dumps({"query": QUERY, "variables": {"login": USER}}).encode()
    request = urllib.request.Request(
        GRAPHQL,
        data=payload,
        headers={
            "Authorization": f"bearer {token()}",
            "Content-Type": "application/json",
            "User-Agent": f"{USER}-profile-readme",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        body = json.load(response)

    # GraphQL reports failures in a 200 body, so this cannot be left to the HTTP status.
    if body.get("errors"):
        raise SystemExit(f"graphql error: {body['errors'][0].get('message')}")
    return body["data"]["user"]["contributionsCollection"]["contributionCalendar"]


def thresholds(counts):
    active = sorted(count for count in counts if count > 0)
    if not active:
        return [1, 2, 3, 4]
    quartiles = [active[int(len(active) * fraction)] for fraction in (0.25, 0.5, 0.75)]
    return [1, max(2, quartiles[0]), max(3, quartiles[1]), max(4, quartiles[2])]


def level_for(count, steps):
    if count <= 0:
        return 0
    for index, step in enumerate(steps):
        if count < step:
            return max(1, index)
    return 4


def escape(value):
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render(calendar):
    weeks = calendar["weeks"]
    total = calendar["totalContributions"]
    counts = [day["contributionCount"] for week in weeks for day in week["contributionDays"]]
    steps = thresholds(counts)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}" role="img" '
        f'aria-label="{total} contributions by {escape(USER)} in the last year">',
        f"<title>{total} contributions in the last year</title>",
        f'<rect width="{WIDTH}" height="{HEIGHT}" rx="18" fill="{BG}"/>',
        f'<rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{HEIGHT - 1}" rx="18" '
        f'fill="none" stroke="{BORDER}" stroke-width="1"/>',
        f'<text x="{GRID_X - 32}" y="38" font-family="{SANS}" font-size="19" '
        f'font-weight="600" fill="{TITLE}">Learn Today. Teach Tomorrow.</text>',
        f'<text x="{WIDTH - 20}" y="38" font-family="{MONO}" font-size="13" '
        f'fill="{MUTED}" text-anchor="end">{total} contributions in the last year</text>',
    ]

    seen_months = set()
    for index, week in enumerate(weeks):
        first = week["contributionDays"][0]
        month = datetime.strptime(first["date"], "%Y-%m-%d").month
        if month not in seen_months and index < len(weeks) - 1:
            seen_months.add(month)
            x = GRID_X + index * PITCH
            parts.append(
                f'<text x="{x}" y="{GRID_Y - 10}" font-family="{MONO}" font-size="11" '
                f'fill="{MUTED}">{MONTHS[month - 1]}</text>'
            )

    for label, row in (("Mon", 1), ("Wed", 3), ("Fri", 5)):
        y = GRID_Y + row * PITCH + CELL - 1
        parts.append(
            f'<text x="{GRID_X - 10}" y="{y}" font-family="{MONO}" font-size="11" '
            f'fill="{MUTED}" text-anchor="end">{label}</text>'
        )

    for index, week in enumerate(weeks):
        x = GRID_X + index * PITCH
        for day in week["contributionDays"]:
            row = datetime.strptime(day["date"], "%Y-%m-%d").weekday()
            row = (row + 1) % 7
            y = GRID_Y + row * PITCH
            count = day["contributionCount"]
            fill = LEVELS[level_for(count, steps)]
            parts.append(
                f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2.5" fill="{fill}">'
                f"<title>{count} on {day['date']}</title></rect>"
            )

    legend_y = GRID_Y + 7 * PITCH + 20
    parts.append(
        f'<text x="{GRID_X - 32}" y="{legend_y + 9}" font-family="{MONO}" font-size="11" '
        f'fill="{MUTED}">Less</text>'
    )
    for index, colour in enumerate(LEVELS):
        x = GRID_X + 12 + index * (CELL + 4)
        parts.append(
            f'<rect x="{x}" y="{legend_y}" width="{CELL}" height="{CELL}" rx="2.5" fill="{colour}"/>'
        )
    parts.append(
        f'<text x="{GRID_X + 12 + len(LEVELS) * (CELL + 4) + 4}" y="{legend_y + 9}" '
        f'font-family="{MONO}" font-size="11" fill="{MUTED}">More</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main():
    try:
        calendar = fetch_calendar()
    except (urllib.error.URLError, OSError, KeyError, TypeError) as error:
        print(f"contribution graph not refreshed: {error}", file=sys.stderr)
        return 0

    svg = render(calendar)
    if GRAPH.exists() and GRAPH.read_text(encoding="utf-8") == svg:
        print("graph unchanged")
        return 0

    GRAPH.write_text(svg, encoding="utf-8")
    print("graph updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
