export function literal(a: bigint) {
  return a < 10n ? a : 10n;
}
export function typedParams(a: bigint, b: bigint) {
  return a < b ? a : b;
}
type Wei = bigint;
export function aliasType(a: Wei, b: Wei) {
  return a > b ? a : b;
}
export function fromCall(x: {value: bigint}, y: {value: bigint}) {
  const a = x.value;
  const b = y.value;
  return a > b ? a : b;
}
export function numbers(a: number, b: number) {
  return a < b ? a : b;
}
