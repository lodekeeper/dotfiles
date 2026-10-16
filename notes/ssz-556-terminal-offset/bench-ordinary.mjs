import fs from "node:fs";
import {execFileSync} from "node:child_process";
import {pathToFileURL} from "node:url";
import ts from "/home/openclaw/ssz/node_modules/typescript/lib/typescript.js";
import * as types from "/home/openclaw/ssz-pr556-terminal-offset/packages/ssz/lib/index.js";
import * as fixed from "/home/openclaw/ssz-pr556-terminal-offset/packages/ssz/lib/type/arrayComposite.js";

const root = "/home/openclaw/ssz-pr556-terminal-offset";
const baselinePath = new URL("./arrayComposite-baseline.mjs", import.meta.url);
let source = execFileSync("git", ["show", "8ac6df0:packages/ssz/src/type/arrayComposite.ts"], {cwd: root, encoding: "utf8"});
for (const [specifier, target] of Object.entries({
  "@chainsafe/persistent-merkle-tree": "/home/openclaw/ssz/packages/persistent-merkle-tree/lib/index.js",
  "./arrayBasic.ts": `${root}/packages/ssz/lib/type/arrayBasic.js`,
})) {
  source = source.replaceAll(JSON.stringify(specifier), JSON.stringify(pathToFileURL(target).href));
}
fs.writeFileSync(baselinePath, ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022}}).outputText);
const baseline = await import(baselinePath.href);
const cases = [
  ["fixed 16 x 40B", new types.ContainerType({root: new types.ByteVectorType(32), value: new types.UintNumberType(8)}), 16],
  ["variable 4 x 100B", new types.ByteListType(100), 4],
];
const result = [];
const runs = 50000;
for (const [name, elementType, count] of cases) {
  const type = new types.ListCompositeType(elementType, 1000);
  const values = Array.from({length: count}, () => elementType instanceof types.ByteListType ? new Uint8Array(100) : elementType.defaultValue());
  const bytes = type.serialize(values);
  const data = {uint8Array: bytes, dataView: new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)};
  for (const mode of ["value", "tree"]) {
    const make = (impl) => mode === "value"
      ? () => impl.value_deserializeFromBytesArrayComposite(elementType, data, 0, bytes.length, type)
      : () => impl.tree_deserializeFromBytesArrayComposite(elementType, type.chunkDepth, data, 0, bytes.length, type);
    const fns = {baseline: make(baseline), fixed: make(fixed)};
    const samples = {baseline: [], fixed: []};
    for (const fn of Object.values(fns)) for (let i = 0; i < 5000; i++) fn();
    for (let round = 0; round < 7; round++) {
      for (const impl of round % 2 ? ["fixed", "baseline"] : ["baseline", "fixed"]) {
        const fn = fns[impl];
        const start = performance.now();
        for (let i = 0; i < runs; i++) fn();
        samples[impl].push((performance.now() - start) * 1e6 / runs);
      }
    }
    const median = (xs) => [...xs].sort((a, b) => a - b)[Math.floor(xs.length / 2)];
    result.push({name, mode, baselineNs: median(samples.baseline), fixedNs: median(samples.fixed), samples});
  }
}
console.log(JSON.stringify({node: process.version, runs, rounds: 7, baseline: "8ac6df0", result}, null, 2));
