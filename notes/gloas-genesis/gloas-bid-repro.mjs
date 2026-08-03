import {ssz} from "/home/openclaw/lodestar/packages/types/lib/index.js";
const hex = (u) => "0x" + Buffer.from(u).toString("hex");

const Bid = ssz.gloas.ExecutionPayloadBid;                 // vanilla: gasLimit = UintNum64 (float64) — the bug
const Exact = new Bid.constructor(                         // exact-uint64 clone (== #9750 fix, == every other client)
  {...Bid.fields, gasLimit: ssz.UintBn64},
  Bid.activeFields,
  {typeName: "ExecutionPayloadBidExact", jsonCase: "eth2"}
);

const exactVal = Exact.defaultValue();
exactVal.gasLimit = 9007199254740993n;                    // 2^53 + 1 (protocol-valid: no gas_limit assert in process_execution_payload_bid)
const wire = Exact.serialize(exactVal);                   // on-wire bid bytes
const vanillaVal = Bid.deserialize(wire);                 // vanilla Lodestar decodes the SAME bytes

console.log("wire bid gasLimit = 2^53+1 =", exactVal.gasLimit.toString());
console.log("vanilla (UintNum64) decodes gasLimit ->", vanillaVal.gasLimit, "(rounded, silent)");
console.log("exact   (UintBn64)  decodes gasLimit ->", exactVal.gasLimit.toString());
const rv = Bid.hashTreeRoot(vanillaVal), re = Exact.hashTreeRoot(exactVal);
console.log("vanilla bid HTR :", hex(rv));
console.log("exact   bid HTR :", hex(re));
console.log("BID ROOTS DIFFER FROM IDENTICAL WIRE BYTES:", hex(rv) !== hex(re));
