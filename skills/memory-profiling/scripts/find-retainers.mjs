#!/usr/bin/env node
/**
 * Find what retains objects of a given constructor name in a V8 heap snapshot.
 * Usage: node find-retainers.mjs <snapshot.heapsnapshot> <constructorName> [limit]
 */
import { readFileSync } from 'fs';

const [file, targetName, limitStr] = process.argv.slice(2);
if (!file || !targetName) { console.error('Usage: node find-retainers.mjs <snap> <name> [limit]'); process.exit(1); }
const limit = parseInt(limitStr) || 20;

console.error(`Parsing ${file}...`);
const raw = JSON.parse(readFileSync(file, 'utf-8'));
const meta = raw.snapshot.meta;
const nodeFields = meta.node_fields;
const edgeFields = meta.edge_fields;
const nodeFieldCount = nodeFields.length;
const edgeFieldCount = edgeFields.length;
const nodes = raw.nodes;
const edges = raw.edges;
const strings = raw.strings;
const nodeTypes = meta.node_types[0];
const edgeTypes = meta.edge_types[0];

const typeIdx = nodeFields.indexOf('type');
const nameIdx = nodeFields.indexOf('name');
const selfSizeIdx = nodeFields.indexOf('self_size');
const edgeCountIdx = nodeFields.indexOf('edge_count');

const eTypeIdx = edgeFields.indexOf('type');
const eNameIdx = edgeFields.indexOf('name_or_index');
const eToIdx = edgeFields.indexOf('to_node');

const nodeCount = nodes.length / nodeFieldCount;

// Build reverse edge map: for each node, who points to it
console.error('Building edge index...');
// First, compute first_edge_index for each node
const firstEdge = new Uint32Array(nodeCount);
let edgeOffset = 0;
for (let i = 0; i < nodeCount; i++) {
  firstEdge[i] = edgeOffset;
  edgeOffset += nodes[i * nodeFieldCount + edgeCountIdx] * edgeFieldCount;
}

// Build retainer map: target_node_index -> [{from_node_index, edge_name}]
console.error('Building retainer map for target nodes...');

// First find target node indices
const targetNodeIndices = new Set();
for (let i = 0; i < nodeCount; i++) {
  const offset = i * nodeFieldCount;
  const typeInt = nodes[offset + typeIdx];
  const nameInt = nodes[offset + nameIdx];
  const typeName = nodeTypes[typeInt];
  const name = strings[nameInt];
  if (name === targetName || `${typeName}::${name}` === targetName) {
    targetNodeIndices.add(i);
  }
}
console.error(`Found ${targetNodeIndices.size} "${targetName}" nodes`);

// Now find all edges that point TO a target node
const retainerInfo = new Map(); // target_node_idx -> [{from_idx, edge_name}]
for (let fromIdx = 0; fromIdx < nodeCount; fromIdx++) {
  const offset = fromIdx * nodeFieldCount;
  const ec = nodes[offset + edgeCountIdx];
  const edgeStart = firstEdge[fromIdx];
  for (let e = 0; e < ec; e++) {
    const eOff = edgeStart + e * edgeFieldCount;
    const toNodeOffset = edges[eOff + eToIdx]; // This is byte offset into nodes array
    const toIdx = toNodeOffset / nodeFieldCount;
    if (targetNodeIndices.has(toIdx)) {
      const eTypeInt = edges[eOff + eTypeIdx];
      const eNameInt = edges[eOff + eNameIdx];
      const edgeType = edgeTypes[eTypeInt];
      const edgeName = edgeType === 'element' || edgeType === 'hidden' ? `[${eNameInt}]` : strings[eNameInt] || `[${eNameInt}]`;
      
      if (!retainerInfo.has(toIdx)) retainerInfo.set(toIdx, []);
      retainerInfo.get(toIdx).push({ fromIdx, edgeName, edgeType });
    }
  }
}

// Aggregate retainer patterns
console.error('Aggregating retainer patterns...');
const patterns = new Map(); // "ParentType::ParentName --edgeName--> Target" -> count
for (const [targetIdx, retainers] of retainerInfo) {
  for (const { fromIdx, edgeName, edgeType } of retainers) {
    const pOffset = fromIdx * nodeFieldCount;
    const pTypeInt = nodes[pOffset + typeIdx];
    const pNameInt = nodes[pOffset + nameIdx];
    const parentType = nodeTypes[pTypeInt];
    const parentName = strings[pNameInt];
    const key = `${parentType}::${parentName} --[${edgeType}:${edgeName}]--> ${targetName}`;
    patterns.set(key, (patterns.get(key) || 0) + 1);
  }
}

// Sort and print
const sorted = [...patterns.entries()].sort((a,b) => b[1] - a[1]);
console.log(`\n=== TOP ${limit} RETAINER PATTERNS FOR "${targetName}" (${targetNodeIndices.size} instances) ===\n`);
for (const [pattern, count] of sorted.slice(0, limit)) {
  console.log(`  ${count.toString().padStart(6)}x  ${pattern}`);
}
