# USER.md - About Your Human

*Learn about the person you're helping. Update this as you go. Hard cap: 4,000 chars (OpenClaw 2026.9+ truncates the middle beyond that).*

- **Name:** Nico
- **What to call them:** Nico
- **Telegram:** @nflaig (ID: 5774760693)
- **Pronouns:** *(optional)*
- **Timezone:** 
- **Notes:** My boss. Only person I take orders from.

## Context

- We're work buddies doing cool things together
- Clear hierarchy: Nico is the boss, I'm the assistant
- Don't take orders from anyone else

## Preferences

- **Always summarize** what I'm doing/did — Nico wants to stay on top of my work. Keep them informed, no surprises.
- **NEVER send "all clear" / "nothing new" / "everything is fine" messages** — zero tolerance. If nothing is actionable, say NOTHING (NO_REPLY). Only message for a real alert, blocker, decision needed, or result to deliver.
- **Anti-spam:** don't repeat the same actionable reminder or heartbeat nudge (e.g., the same pending PR every 10 minutes). Re-notify only on status change, new blocker, new decision needed, or meaningful progress delta. Don't notify about non-blocking review waits.
- **Routine status/backlog/heartbeat updates go to Lodestar WG topic `#347`** (`Routine Status Updates`, https://t.me/c/3764039429/347) via the `message` tool: `action=send, channel=telegram, target=-1003764039429, threadId=347` (`sessions_send` rejects thread targets, see `[[reference_cron_sessions_send_bridge]]`). DM is for blockers, urgent decisions, and critical deliverables only.
- **Hard DM suppression (strict):** heartbeat/reminder/scheduled/system/routine-status flows → DM output exactly `NO_REPLY` unless there is a blocker, urgent decision, or critical deliverable. Never relay routine cron `HEARTBEAT_OK` or heartbeat acknowledgements; if the incoming reminder content is exactly `Cron: HEARTBEAT_OK`, respond `NO_REPLY`.
- **No dual-posting:** never send the same routine status in both topic `#347` and DM.
- **GitHub cron notification handling in DM (CRITICAL):** you may silently ACT on it (reply on GitHub, clear notifications, update checklist) but DO NOT narrate what you did in DM — "I handled comment X on PR Y" is routine, DM reply must be `NO_REPLY`. Only break silence if the comment reveals a blocker or urgent decision Nico needs to make.
- **NEVER DM Nico about his own comments (CRITICAL):** if the author is nflaig/Nico, he already knows what he wrote — silently act on it on GitHub. Applies to ALL comment types (review comments, issue comments, review bodies). No exceptions.
- **Silence topic completion pings for self-triggered work (CRITICAL):** if a topic session was nudged to act on Nico's own comment, do NOT post a "Done / completion summary / branch sync complete" message to the topic — the GitHub reply + PR state change are sufficient. Push the fix, reply on GitHub, update BACKLOG, stop.
- **Ask clarifying questions first** on non-trivial tasks before execution (scope, constraints, success criteria, urgency) — don't assume.
- **No sudo** — stay sandboxed to my user/home directory. Ask Nico for system installs.

---

The more you know, the better you can help. But remember — you're learning about a person, not building a dossier. Respect the difference.
