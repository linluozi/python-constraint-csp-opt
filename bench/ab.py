"""Final A/B benchmark: upstream 2.7.3 vs the optimized solver, strictly interleaved.

Two separate interpreter-level packages cannot be imported into one process, so
each round spawns one subprocess per arm. Within a round the arms are ordered in
a rotating fashion and every arm reports best-of-N. The reported number is the
median of the per-round ratios, which is robust to the position effects that
made single-shot comparisons on this machine unreliable (several tens of
percent).

Usage:
    python ab.py --rounds 5 --out ab.json
"""
import argparse
import json
import os
import statistics
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PY = sys.executable

ARMS = [
    ("upstream", os.path.join(ROOT, "upstream")),
    ("optimized", os.path.join(ROOT, "python-constraint-opt")),
]

RUNNER = r'''
import json, sys, time
sys.path.insert(0, sys.argv[1])
sys.path.insert(0, sys.argv[2])
import run_bench as rb
from constraint.domain import Domain
from constraint.constraints import Constraint

HIDE = [0]; PUSH = [0]
_oh, _op = Domain.hideValue, Domain.pushState
def h(self, v):
    HIDE[0] += 1
    return _oh(self, v)
def p(self):
    PUSH[0] += 1
    return _op(self)

case, mode, reps = sys.argv[3], sys.argv[4], int(sys.argv[5])
build = {
    "queens-8-all": lambda: rb.queens(8),
    "queens-10-all": lambda: rb.queens(10),
    "queens-12-all": lambda: rb.queens(12),
    "queens-16-first": lambda: rb.queens(16),
    "queens-20-first": lambda: rb.queens(20),
    "sudoku-hard": lambda: rb.sudoku(rb.SUDOKU_HARD),
    "dedispersion-all": lambda: rb.dedispersion(),
    "microhh-small-all": lambda: rb.microhh_small(),
    "hotspot-all": lambda: rb.hotspot(),
    "graph-coloring-all": lambda: rb.graph_coloring(16, 0.3, 4, 7),
}[case]

times = []
nsol = None
hide = push = None
for i in range(reps):
    problem = build()
    if i == 0:
        Domain.hideValue, Domain.pushState = h, p
        HIDE[0] = PUSH[0] = 0
    t = time.perf_counter()
    if mode == "all":
        nsol = len(problem.getSolutions())
    else:
        nsol = 1 if problem.getSolution() is not None else 0
    times.append(time.perf_counter() - t)
    if i == 0:
        Domain.hideValue, Domain.pushState = _oh, _op
        hide, push = HIDE[0], PUSH[0]

print(json.dumps(dict(best=min(times), median=statistics.median(times) if False else sorted(times)[len(times)//2],
                      nsol=nsol, hide=hide, push=push)))
'''

CASES = [
    ("queens-8-all", "all"),
    ("queens-10-all", "all"),
    ("queens-12-all", "all"),
    ("queens-16-first", "first"),
    ("queens-20-first", "first"),
    ("sudoku-hard", "first"),
    ("dedispersion-all", "all"),
    ("microhh-small-all", "all"),
    ("hotspot-all", "all"),
    ("graph-coloring-all", "all"),
]


def run_arm(pkg, case, mode, reps):
    """Run one arm (package + case) in a fresh subprocess and return its timings."""
    script = os.path.join(HERE, "_runner_tmp.py")
    with open(script, "w", encoding="utf-8") as fh:
        fh.write(RUNNER)
    out = subprocess.run(
        [PY, script, pkg, HERE, case, mode, str(reps)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800,
    )
    if out.returncode != 0:
        raise RuntimeError(out.stderr[-800:])
    return json.loads(out.stdout.strip().splitlines()[-1])


def main():
    """Parse arguments and run the interleaved upstream-vs-optimized benchmark."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=5)
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--out", default=os.path.join(HERE, "ab.json"))
    ap.add_argument("--cases", default="")
    args = ap.parse_args()

    cases = [c for c in CASES if not args.cases or c[0] in args.cases.split(",")]
    results = []
    for case, mode in cases:
        rounds = []
        for r in range(args.rounds):
            order = ARMS[r % len(ARMS):] + ARMS[: r % len(ARMS)]
            row = {}
            for label, pkg in order:
                try:
                    row[label] = run_arm(pkg, case, mode, args.reps)
                except Exception as exc:  # noqa: BLE001
                    row[label] = {"error": str(exc)[-300:]}
            rounds.append(row)
            print(case, r, {k: (round(v["best"], 4) if "best" in v else "ERR")
                            for k, v in row.items()}, flush=True)

        entry = {"case": case, "mode": mode}
        for label, _ in ARMS:
            vals = [x[label] for x in rounds if "best" in x[label]]
            if not vals:
                entry[label] = {"error": rounds[0][label].get("error")}
                continue
            entry[label] = dict(
                best=round(min(v["best"] for v in vals), 4),
                median=round(statistics.median([v["median"] for v in vals]), 4),
                nsol=vals[0]["nsol"],
                hide=vals[0]["hide"],
                push=vals[0]["push"],
            )
        ratios = [x["optimized"]["best"] / x["upstream"]["best"]
                  for x in rounds if "best" in x["optimized"] and "best" in x["upstream"]]
        if ratios:
            entry["speedup_median"] = round(1.0 / statistics.median(ratios), 3)
            entry["speedup_min"] = round(1.0 / max(ratios), 3)
            entry["speedup_max"] = round(1.0 / min(ratios), 3)
            entry["solutions_agree"] = entry["upstream"]["nsol"] == entry["optimized"]["nsol"]
        results.append(entry)
        print("  ->", case, {k: entry.get(k) for k in ("speedup_median", "solutions_agree")}, flush=True)

    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)
    print("wrote", args.out)


if __name__ == "__main__":
    main()
