#!/usr/bin/env node
/**
 * Post-processes Bruno CLI JSON results to compute p50/p95/p99 latency percentiles.
 *
 * Usage:
 *   bru run bruno/02-latency --env staging --iteration-count 50 --reporter-json results-latency.json
 *   node scripts/analyze-latency.js results-latency.json
 *
 * Exit code 1 if p95 exceeds THRESHOLD_P95_MS.
 */

const fs = require("fs");

const THRESHOLD_P95_MS = 2000; // adjust once baseline prod data is available

function percentile(arr, p) {
  const sorted = [...arr].sort((a, b) => a - b);
  const idx = Math.ceil((p / 100) * sorted.length) - 1;
  return sorted[Math.max(0, idx)];
}

const resultsPath = process.argv[2] || "results-latency.json";
const raw = JSON.parse(fs.readFileSync(resultsPath, "utf-8"));

const timings = (raw.results || [])
  .filter((r) => r.response && r.response.responseTime != null)
  .map((r) => r.response.responseTime);

if (timings.length === 0) {
  console.error("No timing data found in results file.");
  process.exit(1);
}

const p50 = percentile(timings, 50);
const p95 = percentile(timings, 95);
const p99 = percentile(timings, 99);

console.log(`Samples : ${timings.length}`);
console.log(`p50     : ${p50}ms`);
console.log(`p95     : ${p95}ms`);
console.log(`p99     : ${p99}ms`);
console.log(`Threshold (p95): ${THRESHOLD_P95_MS}ms`);

if (p95 > THRESHOLD_P95_MS) {
  console.error(`\nFAIL: p95 (${p95}ms) exceeds threshold (${THRESHOLD_P95_MS}ms)`);
  process.exit(1);
}

console.log(`\nPASS: p95 within threshold.`);
