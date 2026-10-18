"""Strict interleaved measurement: rotate arm order every round, report per-round ratios.

Single-shot comparisons on this machine are unreliable (position effects of
several tens of percent were observed), so no conclusion is drawn from a single
ordering.
"""
import argparse
import json
import statistics
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, r"E:/WorkBuddy-Work/WorkBuddy-0/csp-opt-lab/python-constraint-opt")
sys.path.insert(0, r"E:/WorkBuddy-Work/WorkBuddy-0/csp-opt-lab/bench")

import run_bench as rb  # noqa: E402
from constraint.solvers import OptimizedBacktrackingSolver  # noqa: E402

ARMS = [
    ("static", lambda: OptimizedBacktrackingSolver(dynamic_mrv=False)),
    ("failfirst", lambda: OptimizedBacktrackingSolver(dynamic_mrv="fail-first")),
    ("full", lambda: OptimizedBacktrackingSolver(dynamic_mrv="always")),
    ("default-auto", OptimizedBacktrackingSolver),
]

CASES = {
    "hotspot-all": lambda s: rb.hotspot(s),
    "microhh-small-all": lambda s: rb.microhh_small(s),
    "dedispersion-all": lambda s: rb.dedispersion(s),
    "queens-9-all": lambda s: rb.queens(9, s),
    "queens-16-first": lambda s: rb.queens(16, s),
}


def main():
    """Rotate the arms every round and report the median per-round ratio."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=5)
    ap.add_argument("--cases", default=",".join(CASES))
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    results = {}
    for case in args.cases.split(","):
        build = CASES[case]
        mode = "first" if case.endswith("-first") else "all"
        rounds = []
        for r in range(args.rounds):
            order = ARMS[r % len(ARMS):] + ARMS[: r % len(ARMS)]
            row = {}
            for label, factory in order:
                prob = build(factory())
                t = time.perf_counter()
                if mode == "all":
                    n = len(prob.getSolutions())
                else:
                    n = 1 if prob.getSolution() else 0
                row[label] = time.perf_counter() - t
                row["_" + label] = n
            rounds.append(row)
            print(case, r, {k: round(v, 4) for k, v in row.items() if not k.startswith("_")}, flush=True)

        summary = {}
        for label, _ in ARMS:
            times = [x[label] for x in rounds]
            ratios = [x[label] / x["static"] for x in rounds]
            summary[label] = dict(
                best=round(min(times), 4),
                median=round(statistics.median(times), 4),
                ratio_median=round(statistics.median(ratios), 3),
                ratio_min=round(min(ratios), 3),
                ratio_max=round(max(ratios), 3),
                nsol=rounds[0]["_" + label],
            )
        results[case] = summary
        print("  ->", case, {k: v["ratio_median"] for k, v in summary.items()}, flush=True)

    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(results, fh, indent=2, ensure_ascii=False)
        print("wrote", args.out)


if __name__ == "__main__":
    main()
