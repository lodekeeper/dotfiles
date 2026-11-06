const v8 = require("node:v8");
const retained = new Array(12);
let peak = 0;
function sample() {
  const space = v8.getHeapSpaceStatistics().find((space) => space.space_name === "new_space");
  peak = Math.max(peak, space.space_size);
}
for (let round = 0; round < 100; round++) {
  const batch = new Array(100000);
  for (let i = 0; i < batch.length; i++) batch[i] = {index: i, round, x: i + round, y: round + 0.5};
  retained[round % retained.length] = batch;
  sample();
}
console.log(JSON.stringify({node: process.version, v8: process.versions.v8, nodeOptions: process.env.NODE_OPTIONS, peakNewSpaceBytes: peak, peakNewSpaceMiB: peak / 1048576, retainedArrays: retained.length}));
