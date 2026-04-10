#!/usr/bin/env python3
import json
import subprocess
from pathlib import Path
from datetime import datetime, timezone

STATE_PATH = Path('/home/openclaw/gh-pr-ci-state.json')

BAD_CONCLUSIONS = {"failure", "cancelled", "timed_out", "action_required"}


def run(cmd: str) -> str:
    return subprocess.check_output(cmd, shell=True, text=True, timeout=60)


def load_state() -> dict:
    if not STATE_PATH.exists():
        return {"version": 1, "failures": {}, "updatedAt": None}
    try:
        return json.loads(STATE_PATH.read_text())
    except Exception:
        return {"version": 1, "failures": {}, "updatedAt": None}


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def get_open_prs() -> list[dict]:
    data = run("gh search prs --author lodekeeper --state open --json number,title,url,repository,updatedAt --limit 100")
    return json.loads(data)


def get_head_sha(repo: str, number: int) -> str:
    pr = json.loads(run(f"gh api repos/{repo}/pulls/{number}"))
    return pr["head"]["sha"]


def get_bad_checks(repo: str, sha: str) -> list[dict]:
    checks = json.loads(run(f"gh api repos/{repo}/commits/{sha}/check-runs?per_page=100"))["check_runs"]
    out = []
    for c in checks:
        conclusion = c.get("conclusion")
        if conclusion in BAD_CONCLUSIONS:
            updated = c.get("completed_at") or c.get("started_at") or c.get("created_at")
            out.append(
                {
                    "name": c.get("name"),
                    "conclusion": conclusion,
                    "updatedAt": updated,
                    "url": c.get("html_url"),
                }
            )
    return out


def main() -> int:
    state = load_state()
    known = state.setdefault("failures", {})

    current_keys = set()
    alerts = []

    prs = get_open_prs()
    for pr in prs:
        repo = pr["repository"]["nameWithOwner"]
        number = int(pr["number"])

        try:
            sha = get_head_sha(repo, number)
            bad_checks = get_bad_checks(repo, sha)
        except subprocess.CalledProcessError:
            continue

        for chk in bad_checks:
            key = f"{repo}#{number}|{sha}|{chk['name']}"
            current_keys.add(key)
            prev = known.get(key)
            if prev is None or prev.get("updatedAt") != chk["updatedAt"] or prev.get("conclusion") != chk["conclusion"]:
                alerts.append(
                    {
                        "repo": repo,
                        "pr": number,
                        "sha": sha,
                        "check": chk["name"],
                        "conclusion": chk["conclusion"],
                        "updatedAt": chk["updatedAt"],
                        "url": chk["url"],
                        "title": pr.get("title"),
                        "prUrl": pr.get("url"),
                    }
                )
            known[key] = {
                "repo": repo,
                "pr": number,
                "sha": sha,
                "check": chk["name"],
                "conclusion": chk["conclusion"],
                "updatedAt": chk["updatedAt"],
                "url": chk["url"],
                "lastSeenAt": now_iso(),
            }

    # prune resolved entries (checks no longer present for currently open PR heads)
    for key in list(known.keys()):
        if key not in current_keys:
            del known[key]

    state["updatedAt"] = now_iso()
    save_state(state)

    if not alerts:
        print("NO_REPLY")
        return 0

    print(f"Open PR CI alert: {len(alerts)} new/changed failing check(s) detected.")
    by_pr = {}
    for a in alerts:
        pr_key = f"{a['repo']}#{a['pr']}"
        by_pr.setdefault(pr_key, {"title": a['title'], "prUrl": a['prUrl'], "items": []})
        by_pr[pr_key]["items"].append(a)

    for pr_key, info in by_pr.items():
        print(f"\n- {pr_key}: {info['title']} — {info['prUrl']}")
        for item in info["items"]:
            print(f"  • {item['check']} -> {item['conclusion']} (updated {item['updatedAt']}) {item['url']}")

    print("\nAction: triage failures and create/update BACKLOG only for actionable issues.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
