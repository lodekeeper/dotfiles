declare function getValue(): bigint;
export function fnReturn() {
  const a = getValue();
  const b = getValue();
  return a > b ? a : b;
}
export function annotatedLocal(x: {value: bigint}) {
  const a: bigint = x.value;
  return a > 5n ? a : 5n;
}
export class C {
  total: bigint = 0n;
  cap(limit: bigint) {
    return this.total > limit ? limit : this.total;
  }
}
export function memberAccess(block: {value: bigint}, bid: {value: bigint}) {
  return block.value > bid.value ? block.value : bid.value;
}
