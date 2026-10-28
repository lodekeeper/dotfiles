export function memberAccess(block: {value: bigint}, bid: {value: bigint}): bigint {
  return Math.max(block.value, bid.value);
}
declare function getValue(): bigint;
export function fnReturn() {
  const a = getValue();
  const b = getValue();
  return Math.max(a, b);
}
