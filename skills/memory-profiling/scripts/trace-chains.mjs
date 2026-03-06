#!/usr/bin/env node
/**
 * Find retention chains for a given constructor.
 * Traces back N levels from target objects to find root retaining paths.
 */
import { readFileSync } from 'fs';

const [file, targetName] = process.argv.slice(2);
if (!file || !targetName) { console.error('Usage: node trace-chains.mjs <snap> <name>'); process.exit(1); }

console.error(`Parsing ${file}...`);
const raw = JSON.parse(readFileSync(file, 'utf-8'));
const meta = raw.snapshot.meta;
const nodeFields = meta.node_fields;
const edgeFields = meta.edge_fields;
const nfc = nodeFields.length;
const efc = edgeFields.length;
const nodes = raw.nodes;
const edges = raw.edges;
const strings = raw.strings;
const nodeTypes = meta.node_types[0];
const edgeTypes = meta.edge_types[0];

const typeIdx = nodeFields.indexOf('type');
const nameIdx = nodeFields.indexOf('name');
const ecIdx = nodeFields.indexOf('edge_count');
const eTypeIdx = edgeFields.indexOf('type');
const eNameIdx = edgeFields.indexOf('name_or_index');
const eToIdx = edgeFields.indexOf('to_node');

const nodeCount = nodes.length / nfc;

// Build first-edge-offset
const firstEdge = new Uint32Array(nodeCount);
let eo = 0;
for (let i = 0; i < nodeCount; i++) {
  firstEdge[i] = eo;
  eo += nodes[i * nfc + ecIdx] * efc;
}

// Build reverse edge map: for every node, who has an edge pointing TO it
console.error('Building reverse edge index...');
const retainers = new Map(); // nodeIdx -> [{fromIdx, edgeName, edgeType}]
for (let fromIdx = 0; fromIdx < nodeCount; fromIdx++) {
  const ec = nodes[fromIdx * nfc + ecIdx];
  const es = firstEdge[fromIdx];
  for (let e = 0; e < ec; e++) {
    const eOff = es + e * efc;
    const toIdx = edges[eOff + eToIdx] / nfc;
    const et = edgeTypes[edges[eOff + eTypeIdx]];
    const eni = edges[eOff + eNameIdx];
    const en = (et === 'element' || et === 'hidden') ? `[${eni}]` : (strings[eni] || `[${eni}]`);
    if (!retainers.has(toIdx)) retainers.set(toIdx, []);
    retainers.get(toIdx).push({ fromIdx, edgeName: en, edgeType: et });
  }
}

function nodeName(idx) {
  const o = idx * nfc;
  const t = nodeTypes[nodes[o + typeIdx]];
  const n = strings[nodes[o + nameIdx]];
  return `${t}::${n}`;
}

// Find target nodes
const targets = [];
for (let i = 0; i < nodeCount; i++) {
  const n = strings[nodes[i * nfc + nameIdx]];
  if (n === targetName) targets.push(i);
}
console.error(`Found ${targets.length} "${targetName}" nodes`);

// Trace 4 levels back for first 10 target nodes
const maxTrace = Math.min(targets.length, 10);
const depth = 5;

for (let t = 0; t < maxTrace; t++) {
  console.log(`\n--- ${targetName} #${t} (node index ${targets[t]}) ---`);
  
  function trace(idx, level, visited) {
    if (level >= depth) return;
    const rets = retainers.get(idx) || [];
    // Filter out weak/internal noise
    const meaningful = rets.filter(r => 
      r.edgeType !== 'weak' && 
      !nodeName(r.fromIdx).startsWith('code::') &&
      !nodeName(r.fromIdx).startsWith('hidden::system / CallSiteInfo') &&
      !nodeName(r.fromIdx).startsWith('hidden::system / WeakCell') &&
      !nodeName(r.fromIdx).startsWith('hidden::system / WeakArrayList')
    );
    for (const r of meaningful.slice(0, 3)) {
      if (visited.has(r.fromIdx)) continue;
      visited.add(r.fromIdx);
      const indent = '  '.repeat(level + 1);
      console.log(`${indent}<-- [${r.edgeType}:${r.edgeName}] -- ${nodeName(r.fromIdx)}`);
      trace(r.fromIdx, level + 1, visited);
    }
  }
  
  trace(targets[t], 0, new Set([targets[t]]));
}
