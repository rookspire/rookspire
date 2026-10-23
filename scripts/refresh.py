#!/usr/bin/env python3
"""Regenerate the auto block in README.md — aggregates only.

The repositories I work in are private. This publishes counts and coarse ages
so the page looks alive without leaking names, numbers, titles or commit
subjects from private work.

Runs inside .github/workflows/profile-refresh.yml and only rewrites the text
between the AUTO markers.
"""
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone

TOKEN = os.environ.get("PROFILE_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
REPO = "Yoyokesbeh/izyec-store"
README = "README.md"
BEGIN, END = "<!-- BEGIN:AUTO -->", "<!-- END:AUTO -->"


def api(path):
    req = urllib.request.Request(
        "https://api.github.com" + path,
        headers={
            "Authorization": "Bearer " + TOKEN,
            "Accept": "application/vnd.github+json",
            "User-Agent": "rookspire-profile-refresh",
        },
    )
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)


def ago(stamp: str) -> str:
    try:
        t = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except Exception:
        return "recently"
    secs = (datetime.now(timezone.utc) - t).total_seconds()
    if secs < 3600:
        return f"{max(1, int(secs // 60))}m ago"
    if secs < 86400:
        return f"{int(secs // 3600)}h ago"
    return f"{int(secs // 86400)}d ago"


def main():
    try:
        pulls = api(f"/repos/{REPO}/pulls?state=open&per_page=50")
    except Exception as e:
        print("cannot read the private repo:", e, file=sys.stderr)
        return 1

    queue = 0
    last_state, last_at = "", ""
    for p in pulls:
        try:
            revs = api(f"/repos/{REPO}/pulls/{p['number']}/reviews")
        except Exception:
            revs = []
        mine = [r for r in revs if (r.get("user") or {}).get("login") == "rookspire"]
        if my := mine:
            last = my[-1]
            if last.get("submitted_at", "") > last_at:
                last_at, last_state = last.get("submitted_at", ""), last.get("state", "").lower()
            if last.get("commit_id") != p["head"]["sha"]:
                queue += 1
        elif any((r or {}).get("login") == "rookspire" for r in (p.get("requested_reviewers") or [])):
            queue += 1

    commit_age = ""
    try:
        c = api(f"/repos/{REPO}/commits?per_page=1")[0]
        commit_age = ago(c["commit"]["author"]["date"])
    except Exception:
        pass

    lines = ["### Right now", ""]
    if queue:
        lines.append(f"- **Review queue:** {queue} waiting for me.")
    else:
        lines.append("- **Review queue:** empty. Nothing is waiting on me.")
    if last_state:
        lines.append(f"- **Last verdict:** `{last_state}`, {ago(last_at)}.")
    if commit_age:
        lines.append(f"- **Last commit in the private work:** {commit_age}.")
    lines.append(f"- **Updated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC "
                 f"by [this workflow](.github/workflows/profile-refresh.yml).")
    lines.append("")
    lines.append("<sub>Aggregates only: the repositories I work in are private, so no names, numbers, "
                 "titles or commit subjects appear here.</sub>")
    block = BEGIN + "\n" + "\n".join(lines) + "\n" + END

    text = open(README).read()
    if BEGIN in text and END in text:
        text = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END), block, text, flags=re.S)
    else:
        text = text.rstrip() + "\n\n" + block + "\n"
    open(README, "w").write(text)
    print(block)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
