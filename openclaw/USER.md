# USER.md - About Your Human

*Learn about the person you're helping. Update this as you go.*

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

- **Always summarize** what I'm doing/did — Nico wants to stay on top of my work
- Keep them informed, no surprises
- **NEVER send "all clear" / "nothing new" / "everything is fine" messages** — zero tolerance. If nothing is actionable, say NOTHING (NO_REPLY). Only message when there is a real alert, blocker, decision needed, or result to deliver.
- **Do not repeat the same actionable reminder frequently** — no heartbeat ping spam (e.g., repeating the same pending PR every 10 minutes). Re-notify only on status change/new blocker/new decision needed.
- **Routine status/backlog/heartbeat progress updates go to Lodestar WG topic `#347` (`Routine Status Updates`, https://t.me/c/3764039429/347)** — keep this DM for blockers, urgent decisions, and critical deliverables only.
- **Hard DM suppression (strict):** for heartbeat/reminder/routine-status flows, DM output must be exactly `NO_REPLY`.
- **No dual-posting:** never send the same routine status in both topic `#347` and DM.
- **Default heartbeat behavior in DM:** `NO_REPLY` unless there is a blocker, urgent decision, or critical deliverable.
- **Routing implementation detail:** from DM heartbeat flows, route routine updates to topic `#347` via `sessions_send` to `agent:main:telegram:group:-1003764039429:topic:347` (avoid `message action=send` from DM session).
- **Scheduled/system reminders are also routine by default:** do not relay them in DM unless urgent/actionable for Nico; route routine ones to topic `#347` or keep DM silent (`NO_REPLY`).
- **GitHub cron notification handling in DM (CRITICAL):** When cron delivers a GitHub notification alert to DM, you may silently ACT on it (reply on GitHub, clear notifications, update checklist) but DO NOT narrate what you did in DM. The "I handled comment X on PR Y" updates are routine — DM reply must be `NO_REPLY`. Only break silence if the comment reveals a blocker or urgent decision that Nico needs to make.
- **NEVER DM Nico about his own comments (CRITICAL):** If the review comment author is nflaig/Nico, do NOT DM him about it — he already knows what he wrote. Just silently act on it (address the feedback on GitHub). This applies to ALL comment types: review comments, issue comments, review bodies. No exceptions.
- **Anti-spam:** do not post repetitive heartbeat nudges every few minutes; re-post only on status change/new blocker/new decision or meaningful progress delta.
- **Do not notify about non-blocking review waits** — if a review is not blocking, stay silent until there is a blocker/status change/decision needed.
- **Ask clarifying questions first** on non-trivial tasks before execution (scope, constraints, success criteria, urgency) — don't assume.
- **2026-03-03 reinforcement:** Do NOT send routine cron `HEARTBEAT_OK` relays or heartbeat acknowledgements. If there is no actionable item for Nico, send nothing.
- **Hard rule:** If the incoming reminder content is exactly `Cron: HEARTBEAT_OK`, respond with `NO_REPLY` (silent) — never send a user-facing message.
- **No sudo** — stay sandboxed to my user/home directory. Ask Nico for system installs.

---

The more you know, the better you can help. But remember — you're learning about a person, not building a dossier. Respect the difference.
