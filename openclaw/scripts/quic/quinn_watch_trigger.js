// Condition gate for the quinn advisory watcher automation.
// Fires only when the detector reports a finding key that was not present at the previous check.
// The first successful check only records a baseline. A failing detector alerts on the 2nd consecutive failed check (daily schedule), then weekly.
const res = await exec({ command: "python3 /home/openclaw/.openclaw/workspace/scripts/quic/quinn_advisory_watch.py --brief" });
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
    message: `WATCHER_ERROR: the quinn advisory detector failed ${errs} consecutive checks. Last error: ${out.error}`,
    state: { ...prev, errs },
  });
} else if (!prev.seeded) {
  json({ fire: false, state: { seeded: true, keys: out.keys, errs: 0 } });
} else {
  const fresh = out.keys.filter((k) => !prev.keys.includes(k));
  json({
    fire: fresh.length > 0,
    message: `NEW_FINDINGS: ${JSON.stringify(fresh)}\naction=${out.action}\nrefs=${JSON.stringify(out.refs)}`,
    state: { seeded: true, keys: out.keys, errs: 0 },
  });
}
