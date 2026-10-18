"""Generate the figures for the README from the raw benchmark JSON.

No number in these figures is typed by hand: every bar comes from
bench/ab.json (strictly interleaved A/B run) or bench/policy.json.

Charts are rendered with English labels on purpose: the JPEG/PNG ends up on
GitHub, where CJK glyphs fall back to empty boxes.
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, LogLocator

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "assets")
os.makedirs(OUT, exist_ok=True)

INK = "#2b2119"
PAPER = "#faf6f0"
AMBER = "#c8892b"
TERRACOTTA = "#b4552f"
OLIVE = "#6b6b3a"
MUTED = "#8a7a68"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "text.color": INK,
    "axes.labelcolor": INK,
    "axes.edgecolor": MUTED,
    "xtick.color": MUTED,
    "ytick.color": INK,
    "figure.facecolor": PAPER,
    "axes.facecolor": PAPER,
    "savefig.facecolor": PAPER,
})

PRETTY = {
    "queens-20-first": "20-queens, first solution",
    "sudoku-hard": "Sudoku (hard), first solution",
    "queens-16-first": "16-queens, first solution",
    "queens-12-all": "12-queens, all 14,200",
    "microhh-small-all": "microhh space, all 11,340",
    "graph-coloring-all": "graph colouring, all 8,688",
    "queens-10-all": "10-queens, all 724",
    "dedispersion-all": "dedispersion space, all 11,130",
    "queens-8-all": "8-queens, all 92",
    "hotspot-all": "hotspot space, all 349,853",
}
MODE_TAG = {"first": "one solution", "all": "enumerate"}


def load(name):
    """Load one of the raw benchmark JSON files from bench/."""
    with open(os.path.join(os.path.dirname(HERE), "bench", name), encoding="utf-8") as fh:
        return json.load(fh)


# --------------------------------------------------------------------------- #
# Figure 1: speedup per case (log x axis - ratios span 1.07x to 736x)
# --------------------------------------------------------------------------- #
def fig_speedup():
    """Horizontal bar chart of the speedup of every case (log x axis)."""
    data = load("ab.json")
    rows = sorted(data, key=lambda e: e["speedup_median"])
    labels = [PRETTY.get(e["case"], e["case"]) for e in rows]
    values = [e["speedup_median"] for e in rows]
    colors = [TERRACOTTA if v >= 10 else AMBER for v in values]

    fig, ax = plt.subplots(figsize=(9.6, 5.6))
    y = range(len(rows))
    ax.barh(list(y), values, color=colors, height=0.66, zorder=3)

    ax.set_xscale("log")
    ax.set_xlim(0.85, 2600)
    ax.set_yticks(list(y))
    ax.set_yticklabels(labels, fontsize=9.5)
    ax.tick_params(axis="y", pad=8)
    ax.set_xlabel("Speedup vs upstream 2.7.3  (log scale, higher is better)", fontsize=10)
    ax.axvline(1.0, color=MUTED, lw=1.1, ls=(0, (4, 3)), zorder=2)

    # Large bars carry their label inside; short bars would push the text past
    # the axis, so those get an outside label instead.
    for yi, v in zip(y, values):
        txt = f"{v:.0f}x" if v >= 10 else f"{v:.2f}x"
        if v >= 3:
            ax.text(v * 0.93, yi, txt, va="center", ha="right",
                    color=PAPER, fontsize=9, fontweight="bold", zorder=4)
        else:
            ax.text(v * 1.06, yi, txt, va="center", ha="left",
                    color=INK, fontsize=9, fontweight="bold", zorder=4)

    ax.grid(axis="x", color=MUTED, alpha=0.22, lw=0.7, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)

    handles = [
        plt.Rectangle((0, 0), 1, 1, color=TERRACOTTA),
        plt.Rectangle((0, 0), 1, 1, color=AMBER),
        plt.Line2D([0], [0], color=MUTED, lw=1.1, ls=(0, (4, 3))),
    ]
    ax.legend(handles, ["10x or more", "below 10x", "upstream baseline"],
              loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=3,
              frameon=False, fontsize=9)

    ax.set_title("Solver speedup by case (median of per-round ratios, 5 interleaved rounds)",
                 fontsize=11.5, pad=12, loc="left")
    fig.tight_layout(rect=(0.012, 0, 1, 0.99))
    path = os.path.join(OUT, "speedup_by_case.png")
    fig.savefig(path, dpi=170)
    plt.close(fig)
    print("wrote", path)


# --------------------------------------------------------------------------- #
# Figure 2: absolute wall clock, upstream vs optimized (log-log)
# --------------------------------------------------------------------------- #
def fig_absolute():
    """Paired bars of the absolute wall clock, upstream vs optimized."""
    data = load("ab.json")
    rows = sorted(data, key=lambda e: e["upstream"]["best"], reverse=True)
    labels = [PRETTY.get(e["case"], e["case"]) for e in rows]
    up = [e["upstream"]["best"] for e in rows]
    opt = [e["optimized"]["best"] for e in rows]

    fig, ax = plt.subplots(figsize=(9.6, 5.6))
    y = list(range(len(rows)))
    h = 0.36
    # Two bars per row must be distinguishable at a glance: a neutral warm grey
    # against a saturated terracotta, not two muted earth tones.
    ax.barh([i + h / 2 for i in y], up, height=h, color="#b9ab99",
            edgecolor=MUTED, lw=0.5, label="upstream 2.7.3", zorder=3)
    ax.barh([i - h / 2 for i in y], opt, height=h, color=TERRACOTTA,
            label="optimized", zorder=3)

    ax.set_xscale("log")
    ax.set_xlim(4e-4, 40)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=9.5)
    ax.tick_params(axis="y", pad=8)
    ax.set_xlabel("Wall clock, best of 2 (seconds, log scale)", fontsize=10)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
    ax.xaxis.set_minor_locator(LogLocator(base=10, subs=()))

    for yi, v in zip([i + h / 2 for i in y], up):
        ax.text(v * 1.09, yi, f"{v:.3g}s", va="center", ha="left", color=INK, fontsize=8)
    for yi, v in zip([i - h / 2 for i in y], opt):
        ax.text(v * 1.09, yi, f"{v:.3g}s", va="center", ha="left", color=TERRACOTTA, fontsize=8)

    ax.grid(axis="x", color=MUTED, alpha=0.22, lw=0.7, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=2,
              frameon=False, fontsize=9)
    ax.set_title("Absolute time to finish the same search (identical solution sets)",
                 fontsize=11.5, pad=12, loc="left")
    fig.tight_layout(rect=(0.012, 0, 1, 0.99))
    path = os.path.join(OUT, "absolute_time.png")
    fig.savefig(path, dpi=170)
    plt.close(fig)
    print("wrote", path)


# --------------------------------------------------------------------------- #
# Figure 3: deterministic counters - domain state saves removed
# --------------------------------------------------------------------------- #
def fig_counters():
    """Paired bars of Domain.pushState calls, upstream vs optimized."""
    data = load("ab.json")
    rows = [e for e in data if e["upstream"]["push"] > 0]
    rows.sort(key=lambda e: e["upstream"]["push"], reverse=True)
    labels = [PRETTY.get(e["case"], e["case"]) for e in rows]
    up = [e["upstream"]["push"] for e in rows]
    opt = [e["optimized"]["push"] for e in rows]

    fig, ax = plt.subplots(figsize=(9.6, 5.4))
    y = list(range(len(rows)))
    h = 0.36
    ax.barh([i + h / 2 for i in y], up, height=h, color="#b9ab99",
            edgecolor=MUTED, lw=0.5, label="upstream 2.7.3", zorder=3)
    ax.barh([i - h / 2 for i in y], opt, height=h, color=TERRACOTTA,
            label="optimized", zorder=3)

    ax.set_xscale("log")
    ax.set_xlim(100, 2e8)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=9.5)
    ax.tick_params(axis="y", pad=8)
    ax.set_xlabel("Domain.pushState() calls  (deterministic, identical on every run, log scale)",
                  fontsize=9.5)
    ax.xaxis.set_major_formatter(FuncFormatter(
        lambda v, _: f"{v/1e6:.0f}M" if v >= 1e6 else (f"{v/1e3:.0f}k" if v >= 1e3 else f"{v:g}")))

    def human(v):
        if v >= 1e6:
            return f"{v/1e6:.1f}M"
        if v >= 1e3:
            return f"{v/1e3:.1f}k"
        return f"{v:g}"

    for yi, v in zip([i + h / 2 for i in y], up):
        ax.text(v * 1.12, yi, human(v), va="center", ha="left", color=INK, fontsize=8)
    for yi, v, base in zip([i - h / 2 for i in y], opt, up):
        cut = 100 * (1 - v / base)
        # Rounding a 99.9% cut to "-100%" reads as "not doing the work at all",
        # so the last tenth is kept.
        cut_txt = "-99.9%" if cut > 99.5 else f"-{cut:.0f}%"
        ax.text(v * 1.12, yi, f"{human(v)}  ({cut_txt})", va="center", ha="left",
                color=TERRACOTTA, fontsize=8)

    ax.grid(axis="x", color=MUTED, alpha=0.22, lw=0.7, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=2,
              frameon=False, fontsize=9)
    ax.set_title("Forward checking only saves the domains a constraint can prune",
                 fontsize=11.5, pad=12, loc="left")
    fig.tight_layout(rect=(0.012, 0, 1, 0.99))
    path = os.path.join(OUT, "pushstate_calls.png")
    fig.savefig(path, dpi=170)
    plt.close(fig)
    print("wrote", path)


if __name__ == "__main__":
    fig_speedup()
    fig_absolute()
    fig_counters()
