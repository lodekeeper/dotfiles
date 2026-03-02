#!/usr/bin/env node
import { readFileSync } from 'fs';

function parseSnapshot(filepath) {
  console.error(`Parsing ${filepath}...`);
  const raw = JSON.parse(readFileSync(filepath, 'utf-8'));
  const nodeFields = raw.snapshot.meta.node_fields;
  const nodeFieldCount = nodeFields.length;
  const nodes = raw.nodes;
  const strings = raw.strings;
  const typeIdx = nodeFields.indexOf('type');
  const nameIdx = nodeFields.indexOf('name');
  const selfSizeIdx = nodeFields.indexOf('self_size');
  const nodeTypes = raw.snapshot.meta.node_types[0];
  const stats = new Map();
  const nodeCount = nodes.length / nodeFieldCount;
  for (let i = 0; i < nodeCount; i++) {
    const offset = i * nodeFieldCount;
    const typeInt = nodes[offset + typeIdx];
    const nameInt = nodes[offset + nameIdx];
    const selfSize = nodes[offset + selfSizeIdx];
    const typeName = nodeTypes[typeInt] || 'unknown';
    const name = strings[nameInt] || '(anonymous)';
    const key = `${typeName}::${name}`;
    const existing = stats.get(key) || { count: 0, selfSize: 0 };
    existing.count++;
    existing.selfSize += selfSize;
    stats.set(key, existing);
  }
  return { stats, nodeCount, filepath };
}

function diffSnapshots(s1, s2) {
  const diffs = [];
  const allKeys = new Set([...s1.stats.keys(), ...s2.stats.keys()]);
  for (const key of allKeys) {
    const a = s1.stats.get(key) || { count: 0, selfSize: 0 };
    const b = s2.stats.get(key) || { count: 0, selfSize: 0 };
    const countDiff = b.count - a.count;
    const selfSizeDiff = b.selfSize - a.selfSize;
    if (Math.abs(selfSizeDiff) > 1000 || Math.abs(countDiff) > 10) {
      diffs.push({ key, countDiff, selfSizeDiff, countA: a.count, countB: b.count, selfSizeA: a.selfSize, selfSizeB: b.selfSize });
    }
  }
  return diffs;
}

function fmt(bytes) {
  if (Math.abs(bytes) < 1024) return `${bytes} B`;
  if (Math.abs(bytes) < 1024*1024) return `${(bytes/1024).toFixed(1)} KB`;
  return `${(bytes/(1024*1024)).toFixed(1)} MB`;
}

const [file1, file2] = process.argv.slice(2);
if (!file1 || !file2) { console.error('Usage: node analyze-heap.mjs <snap1> <snap2>'); process.exit(1); }

const snap1 = parseSnapshot(file1);
const snap2 = parseSnapshot(file2);
console.log(`\nSnap1: ${snap1.nodeCount} nodes`);
console.log(`Snap2: ${snap2.nodeCount} nodes`);
console.log(`Diff: +${snap2.nodeCount - snap1.nodeCount}\n`);

const diffs = diffSnapshots(snap1, snap2);
diffs.sort((a, b) => b.selfSizeDiff - a.selfSizeDiff);
console.log('=== TOP 40 BY SELF-SIZE GROWTH ===');
console.log('Type::Name'.padEnd(60) + '| Count Δ    | Self Δ         | Count');
console.log('-'.repeat(120));
for (const d of diffs.slice(0, 40)) {
  const n = d.key.length > 58 ? d.key.slice(0,55)+'...' : d.key.padEnd(60);
  const cd = (d.countDiff>=0?'+':'')+d.countDiff;
  console.log(`${n}| ${cd.padStart(10)} | ${fmt(d.selfSizeDiff).padStart(14)} | ${d.countA}→${d.countB}`);
}

console.log('\n=== TOP 40 BY COUNT GROWTH ===');
diffs.sort((a, b) => b.countDiff - a.countDiff);
console.log('Type::Name'.padEnd(60) + '| Count Δ    | Self Δ         | Count');
console.log('-'.repeat(120));
for (const d of diffs.slice(0, 40)) {
  const n = d.key.length > 58 ? d.key.slice(0,55)+'...' : d.key.padEnd(60);
  const cd = (d.countDiff>=0?'+':'')+d.countDiff;
  console.log(`${n}| ${cd.padStart(10)} | ${fmt(d.selfSizeDiff).padStart(14)} | ${d.countA}→${d.countB}`);
}
