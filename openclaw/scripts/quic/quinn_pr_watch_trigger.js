// Condition gate for the quinn PR security-review automation.
// Fires when a non-trivial quinn PR is new or has a new head commit, or when a commit without a PR lands on main / 0.11.x.
// The first successful check fires once with the backfill set: open PRs updated in the last 30 days, plus anything
// merged after the latest quinn-proto release. Everything else seen on that check becomes the baseline.
// A failing detector alerts on the 2nd consecutive failed check (daily schedule), then weekly.
const res = await exec({ command: "python3 /home/openclaw/.openclaw/workspace/scripts/quic/quinn_pr_watch.py" });
const raw = String(res?.aggregated ?? "").trim();
let out;
try {
  out = JSON.parse(raw.split("\n").pop());
} catch {
  out = { ok: false, error: `unparseable detector output: ${raw.slice(0, 300)}` };
}
const prev = trigger.state ?? {};
if (!out.ok) {
  const errs = (prev.errs ?? 0) + 1;
  json({
    fire: errs === 2 || errs % 7 === 0,
    message: `WATCHER_ERROR: the quinn PR detector failed ${errs} consecutive checks. Last error: ${out.error}`,
    state: { ...prev, errs },
  });
} else {
  const seen = new Map(prev.seen ?? []);
  const fresh = out.items.filter((i) => !i.trivial && (prev.seeded ? seen.get(i.id) !== i.sha : i.backfill));
  for (const i of out.items) {
    seen.delete(i.id);
    seen.set(i.id, i.sha);
  }
  const lines = fresh.map((i) => `- ${i.id} @${i.sha} [${i.state} -> ${i.base}] ${i.title} ${i.url}`);
  json({
    fire: fresh.length > 0,
    message: `${prev.seeded ? "NEW_CHANGES" : "BACKFILL"} (${fresh.length}); latest released quinn-proto ${out.latest_quinn_proto} at ${out.latest_quinn_proto_at}:\n${lines.join("\n")}`,
    state: { seeded: true, seen: [...seen].slice(-400), errs: 0 },
  });
}
