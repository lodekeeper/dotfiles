// Delete every QMD vector (content_vectors + vectors_vec) for the given content hashes so the next
// `qmd embed` re-queues them. qmd 1.0.7 only re-queues hashes missing seq 0, so a hash that was cut
// off mid-document by the 30-min embed-session cap stays partial forever unless cleared like this.
// Must run under qmd's own Node install (better-sqlite3 is ABI-bound to it):
//   ~/.nvm/versions/node/v22.22.0/bin/node scripts/memory/qmd_clear_hash_vectors.mjs <index.sqlite> <hash>...
import { createRequire } from "node:module";
import { homedir } from "node:os";

const qmdPkgDir =
  process.env.QMD_PKG_DIR ?? `${homedir()}/.nvm/versions/node/v22.22.0/lib/node_modules/@tobilu/qmd`;
const require = createRequire(`${qmdPkgDir}/package.json`);
const Database = require("better-sqlite3");
const sqliteVec = require("sqlite-vec");

const [indexPath, ...hashes] = process.argv.slice(2);
if (!indexPath || hashes.length === 0) {
  console.error("usage: qmd_clear_hash_vectors.mjs <index.sqlite> <hash>...");
  process.exit(2);
}
for (const hash of hashes) {
  if (!/^[0-9a-f]{64}$/.test(hash)) {
    console.error(`refusing non-sha256 hash: ${hash}`);
    process.exit(2);
  }
}

const db = new Database(indexPath);
sqliteVec.load(db);
// Same deletion shape as qmd's own cleanupOrphanedVectors (vectors_vec first, keyed by hash_seq).
const delVec = db.prepare(
  "DELETE FROM vectors_vec WHERE hash_seq IN (SELECT hash || '_' || seq FROM content_vectors WHERE hash = ?)"
);
const delContent = db.prepare("DELETE FROM content_vectors WHERE hash = ?");
const clear = db.transaction((hs) => {
  let rows = 0;
  for (const h of hs) {
    delVec.run(h);
    rows += delContent.run(h).changes;
  }
  return rows;
});
const rows = clear(hashes);
db.close();
console.log(`cleared ${rows} content_vectors rows across ${hashes.length} hash(es)`);
