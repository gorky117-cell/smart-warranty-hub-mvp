from __future__ import annotations

import math
from typing import Dict, Iterable, List, Sequence, Tuple


def safe_pct(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return (numerator / denominator) * 100.0


def percentile(values: Sequence[float], q: float) -> float:
    vals = sorted(float(v) for v in values)
    if not vals:
        return 0.0
    if len(vals) == 1:
        return vals[0]
    q = max(0.0, min(1.0, float(q)))
    pos = q * (len(vals) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(vals) - 1)
    frac = pos - lo
    return vals[lo] * (1.0 - frac) + vals[hi] * frac


def brier_score(predictions: Sequence[float], outcomes: Sequence[int]) -> float:
    pairs = list(zip(predictions, outcomes))
    if not pairs:
        return 0.0
    total = 0.0
    for pred, out in pairs:
        p = max(0.0, min(1.0, float(pred)))
        y = 1.0 if int(out) else 0.0
        total += (p - y) ** 2
    return total / len(pairs)


def expected_calibration_error(predictions: Sequence[float], outcomes: Sequence[int], bins: int = 10) -> float:
    pairs = list(zip(predictions, outcomes))
    if not pairs:
        return 0.0
    bins = max(2, int(bins))
    total = len(pairs)
    ece = 0.0
    for b in range(bins):
        lo = b / bins
        hi = (b + 1) / bins
        bucket: List[Tuple[float, int]] = []
        for pred, out in pairs:
            p = max(0.0, min(1.0, float(pred)))
            if b == bins - 1:
                ok = lo <= p <= hi
            else:
                ok = lo <= p < hi
            if ok:
                bucket.append((p, int(out)))
        if not bucket:
            continue
        avg_conf = sum(p for p, _ in bucket) / len(bucket)
        avg_acc = sum(1.0 if y else 0.0 for _, y in bucket) / len(bucket)
        ece += abs(avg_acc - avg_conf) * (len(bucket) / total)
    return ece


def population_stability_index(expected: Sequence[float], actual: Sequence[float], bins: int = 10) -> float:
    if not expected or not actual:
        return 0.0
    bins = max(2, int(bins))
    eps = 1e-6
    edges = [i / bins for i in range(bins + 1)]

    def _bucket_counts(values: Sequence[float]) -> List[int]:
        out = [0 for _ in range(bins)]
        for raw in values:
            v = max(0.0, min(1.0, float(raw)))
            idx = min(int(v * bins), bins - 1)
            if v == 1.0:
                idx = bins - 1
            if not (edges[idx] <= v <= edges[idx + 1]):
                continue
            out[idx] += 1
        return out

    expected_counts = _bucket_counts(expected)
    actual_counts = _bucket_counts(actual)
    e_total = max(1, sum(expected_counts))
    a_total = max(1, sum(actual_counts))

    psi = 0.0
    for e_cnt, a_cnt in zip(expected_counts, actual_counts):
        e_ratio = max(eps, e_cnt / e_total)
        a_ratio = max(eps, a_cnt / a_total)
        psi += (a_ratio - e_ratio) * math.log(a_ratio / e_ratio)
    return psi


def variant_balance_gap(counts: Dict[str, int]) -> int:
    if not counts:
        return 0
    values = [int(v) for v in counts.values()]
    return max(values) - min(values)
