// One-shot gate: fires once a @chainsafe/libp2p-quic release newer than 2.1.4 is published on npm.
const res = await exec({
  command: "curl -sf https://registry.npmjs.org/@chainsafe%2flibp2p-quic/latest | python3 -c 'import json,sys; print(json.load(sys.stdin)[\"version\"])'",
});
const version = String(res?.aggregated ?? "").trim().split("\n").pop();
const parts = version.split(".").map(Number);
const valid = parts.length === 3 && parts.every(Number.isInteger);
const [major, minor, patch] = parts;
const newer = valid && (major > 2 || (major === 2 && (minor > 1 || (minor === 1 && patch > 4))));
json({
  fire: newer,
  message: `@chainsafe/libp2p-quic ${version} is published on npm; Lodestar unstable still depends on ^2.1.4.`,
  state: { last: version },
});
