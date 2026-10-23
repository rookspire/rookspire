#!/usr/bin/env python3
"""Regenerate the auto-updating block in README.md from the GitHub API.

Runs inside the profile-refresh workflow. Writes only between the AUTO markers,
so hand-written prose around it is never touched.
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


def short(sha):
    return sha[:7]


def main():
    lines = []
    try:
        pulls = api(f"/repos/{REPO}/pulls?state=open&per_page=30")
    except Exception as e:
        print("cannot read repo:", e, file=sys.stderr)
        return 1

    awaiting, reviewed = [], []
    for p in pulls:
        try:
            revs = api(f"/repos/{REPO}/pulls/{p['number']}/reviews")
        except Exception:
            revs = []
        mine = [r for r in revs if (r.get("user") or {}).get("login") == "rookspire"]
        if not mine:
            # requested but never reviewed, or a fresh request after my last verdict
            if any((r or {}).get("login") == "rookspire" for r in (p.get("requested_reviewers") or [])):
                awaiting.append((p, None))
            continue
        last = mine[-1]
        reviewed.append((p["number"], p["title"], last["state"].lower(), last["commit_id"]))
        # a new commit after my verdict means it is back in my queue
        if last["commit_id"] != p["head"]["sha"]:
            awaiting.append((p, last))

    last_commit = ""
    try:
        c = api(f"/repos/{REPO}/commits?per_page=1")[0]
        last_commit = f"`{short(c['sha'])}` — {c['commit']['message'].splitlines()[0]} ({c['commit']['author']['date'][:10]})"
    except Exception:
        pass

    lines.append("### Right now")
    lines.append("")
    if awaiting:
        for p, last in awaiting:
            why = "new commits since my last verdict" if last else "not yet reviewed"
            lines.append(f"- **Awaiting my review:** [#{p['number']}]({p['html_url']}) — {p['title']} *({why})*")
    else:
        lines.append("- **Awaiting my review:** nothing. The queue is empty.")
    for num, title, state, sha in reviewed[:3]:
        lines.append(f"- **Last verdict on #{num}:** `{state}` at `{short(sha)}` — {title}")
    if last_commit:
        lines.append(f"- **Latest on `izyec-store`:** {last_commit}")
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines.append(f"- **Refreshed:** {stamp} by [this workflow](.github/workflows/profile-refresh.yml)")
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
