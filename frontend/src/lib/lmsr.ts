/**
 * Client-side LMSR (Logarithmic Market Scoring Rule) implementation.
 * Used for cost estimation in the trade ticket UI before submitting to backend.
 * Mirrors the Go implementation in internal/lmsr/lmsr.go.
 *
 * Reference: Hanson, R. (2003) "Combinatorial Information Market Design"
 */

/** Log-sum-exp trick for numerical stability. */
function logSumExp(xs: number[]): number {
  if (xs.length === 0) return -Infinity;
  const maxVal = Math.max(...xs);
  if (!isFinite(maxVal)) return -Infinity;
  let sum = 0;
  for (const x of xs) {
    sum += Math.exp(x - maxVal);
  }
  return maxVal + Math.log(sum);
}

/** LMSR cost function: C(q) = b * ln(exp(qYes/b) + exp(qNo/b)). */
export function cost(qYes: number, qNo: number, b: number): number {
  return b * logSumExp([qYes / b, qNo / b]);
}

/** Instantaneous price (probability) for YES outcome. */
export function price(qYes: number, qNo: number, b: number): number {
  const yOverB = qYes / b;
  const nOverB = qNo / b;
  const maxVal = Math.max(yOverB, nOverB);
  const expYes = Math.exp(yOverB - maxVal);
  const expNo = Math.exp(nOverB - maxVal);
  return expYes / (expYes + expNo);
}

/** Instantaneous price for NO outcome: 1 - price(YES). */
export function priceNo(qYes: number, qNo: number, b: number): number {
  return 1 - price(qYes, qNo, b);
}

/**
 * Cost to trade `delta` shares of `side`.
 * Positive delta = buy, negative delta = sell.
 */
export function tradeCost(
  qYes: number,
  qNo: number,
  b: number,
  delta: number,
  side: "YES" | "NO"
): number {
  const costBefore = cost(qYes, qNo, b);
  if (side === "YES") {
    return cost(qYes + delta, qNo, b) - costBefore;
  }
  return cost(qYes, qNo + delta, b) - costBefore;
}

/** Average execution price per share for a trade. */
export function fillPrice(
  qYes: number,
  qNo: number,
  b: number,
  delta: number,
  side: "YES" | "NO"
): number {
  if (delta === 0) return side === "YES" ? price(qYes, qNo, b) : priceNo(qYes, qNo, b);
  const tc = tradeCost(qYes, qNo, b, delta, side);
  return tc / delta;
}
