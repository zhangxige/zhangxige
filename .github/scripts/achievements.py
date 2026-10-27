#!/usr/bin/env python3
"""Generate a compact achievements card for a GitHub profile.

Data sources
------------
- api.github.com (REST, uses GITHUB_TOKEN when available) -> repos / account age
- github-contributions-api.jogruber.de -> contribution calendar (no auth needed)

Outputs
-------
assets/achievements-light.svg
assets/achievements-dark.svg

The SVGs are committed to the repository, so the profile never depends on a
third-party image service at view time.
"""
from __future__ import annotations

import html
import json
import os
import sys
import urllib.request
from datetime import datetime

USER = os.environ.get("GH_USER", "zhangxige")
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
# Overridable only so the card can be rendered locally from behind a proxy.
API_BASE = os.environ.get("GH_API_BASE", "https://api.github.com").rstrip("/")
CONTRIB_API = os.environ.get(
    "CONTRIB_API",
    "https://github-contributions-api.jogruber.de/v4/{user}?y=all",
)
OUT_DIR = os.environ.get("OUT_DIR", "assets")
TIMEOUT = 30

FONT = '-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif'
PALETTES = {
    "light": {"text": "#1F2328", "muted": "#656D76", "accent": "#BF8700", "line": "#D8DEE4"},
    "dark": {"text": "#E6EDF3", "muted": "#8B949E", "accent": "#E3B341", "line": "#30363D"},
}


def log(message: str) -> None:
    print(message, file=sys.stderr)


def http_get(url: str, token: str = "") -> str:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "profile-achievements-card"},
    )
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return response.read().decode("utf-8", "replace")


def github(path: str):
    return json.loads(http_get(API_BASE + path, token=TOKEN))


def collect() -> dict:
    year = datetime.now().year
    stats = {
        "repos": None,
        "since": None,
        "years": None,
        "contrib_all": None,
        "contrib_year": None,
        "year": year,
    }

    try:
        user = github(f"/users/{USER}")
        stats["repos"] = user.get("public_repos")
        created = user.get("created_at") or ""
        if len(created) >= 4 and created[:4].isdigit():
            stats["since"] = int(created[:4])
            stats["years"] = max(year - stats["since"], 1)
    except Exception as error:  # noqa: BLE001 - keep the last good card on failure
        log(f"warning: could not read user profile: {error}")

    # Third-party call, never gets the token.
    try:
        payload = json.loads(http_get(CONTRIB_API.format(user=USER)))
        totals = payload.get("total") or {}
        stats["contrib_all"] = sum(v for v in totals.values() if isinstance(v, int))
        stats["contrib_year"] = totals.get(str(year))
    except Exception as error:  # noqa: BLE001
        log(f"warning: could not read contribution calendar: {error}")

    return stats


def fmt(value) -> str:
    return "—" if value is None else f"{value:,}"


def render(blocks, palette, title: str) -> str:
    width, height = 860, 128
    pad = 24
    inner = width - pad * 2
    step = inner / len(blocks)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(title)}">',
        f"<title>{html.escape(title)}</title>",
        f"<style>text{{font-family:{FONT}}}</style>",
    ]

    for index in range(1, len(blocks)):
        x = round(pad + step * index, 1)
        parts.append(
            f'<line x1="{x}" y1="40" x2="{x}" y2="106" '
            f'stroke="{palette["line"]}" stroke-width="1"/>'
        )

    for index, (value, label) in enumerate(blocks):
        cx = round(pad + step * (index + 0.5), 1)
        parts.append(f'<rect x="{cx - 10}" y="32" width="20" height="3" rx="1.5" fill="{palette["accent"]}"/>')
        parts.append(
            f'<text x="{cx}" y="74" text-anchor="middle" font-size="30" font-weight="700" '
            f'fill="{palette["text"]}">{html.escape(value)}</text>'
        )
        parts.append(
            f'<text x="{cx}" y="98" text-anchor="middle" font-size="12" letter-spacing="0.6" '
            f'fill="{palette["muted"]}">{html.escape(label)}</text>'
        )

    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main() -> int:
    stats = collect()
    if all(stats[key] is None for key in ("contrib_all", "contrib_year", "repos", "years")):
        log("error: no data available, keeping the previous card")
        return 1

    blocks = [
        (fmt(stats["contrib_all"]), "CONTRIBUTIONS"),
        (fmt(stats["contrib_year"]), f"IN {stats['year']}"),
        (fmt(stats["repos"]), "PUBLIC REPOS"),
        (fmt(stats["years"]), "YEARS ON GITHUB"),
    ]
    title = (
        f"GitHub achievements: {fmt(stats['contrib_all'])} contributions, "
        f"{fmt(stats['repos'])} public repositories, {fmt(stats['years'])} years on GitHub"
    )

    os.makedirs(OUT_DIR, exist_ok=True)
    for theme, palette in PALETTES.items():
        path = os.path.join(OUT_DIR, f"achievements-{theme}.svg")
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(render(blocks, palette, title))
        log(f"wrote {path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
