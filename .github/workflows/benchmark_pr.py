"""Compare two pytest-benchmark JSON files and produce a markdown table.

Usage:
    python benchmark_pr.py <old.json> <new.json> <output.md> [header]

The table reports mean ± standard deviation for human readability, but the
pass/fail gate compares the *median*. Median is robust to a single outlier round
in either direction: `min` is biased down by an accidentally-fast run, `mean` up
by an unlucky-slow one (a transient OS/GC spike). With >=3 rounds the median
ignores one such spike, which is what keeps the noisy single-action benchmarks
from tripping the gate spuriously.

Exits with code 1 if any benchmark's median regresses by more than
REGRESSION_THRESHOLD percent.
"""

import json
import os
import sys

import pandas as pd

REGRESSION_THRESHOLD = 50  # percent


def load_stats(path):
    with open(path) as f:
        data = json.load(f)

    commit = data["commit_info"]["id"]

    rows = []
    for d in data["benchmarks"]:
        s = d["stats"]
        rows.append(
            {
                "Benchmark": d["name"],
                "median": s["median"],
                "mean": s["mean"],
                "stddev": s["stddev"],
            }
        )

    return commit, pd.DataFrame(rows)


def _fmt(mean, std):
    return f"{mean:.5f} ± {std:.5f}"


def _write(out_file, report):
    with open(out_file, "w") as f:
        f.write(report)
    print(report)  # noqa: T201


def make_report(old_path, new_path, out_file, header=None):
    new_commit, new_df = load_stats(new_path)

    # No baseline available (e.g. the first PR introducing benchmarks, or a run on
    # a base commit that predates the suite). Report HEAD-only numbers and pass.
    if not os.path.exists(old_path) or os.path.getsize(old_path) == 0:
        df = pd.DataFrame(
            {
                "Benchmark": new_df["Benchmark"],
                f"Median (s) HEAD {new_commit}": new_df["median"].map("{:.5f}".format),
                f"Mean ± SD (s) HEAD {new_commit}": [
                    _fmt(m, s)
                    for m, s in zip(new_df["mean"], new_df["stddev"], strict=True)
                ],
            }
        )
        # disable_numparse: see note on the comparison table below.
        report = df.to_markdown(index=False, disable_numparse=True)
        note = "_No baseline found; showing HEAD results only (no comparison)._"
        report = f"{note}\n\n{report}"
        if header:
            report = f"## {header}\n\n{report}"
        _write(out_file, report)
        return

    old_commit, old_df = load_stats(old_path)

    # Merge on benchmark name (drops benchmarks present on only one side).
    merged = old_df.merge(new_df, on="Benchmark", suffixes=("_old", "_new"))

    # Gate on the median (see module docstring).
    pct_change = (
        100 * (merged["median_new"] - merged["median_old"]) / merged["median_old"]
    )

    # Median columns first: they drive the gate, so "Median Change" is verifiable
    # straight from them. Mean ± SD follows as a noise indicator (a wide SD or a mean
    # far from the median flags a spiky benchmark whose median we're rightly trusting).
    df = pd.DataFrame(
        {
            "Benchmark": merged["Benchmark"],
            f"Median (s) BASE {old_commit}": merged["median_old"].map("{:.5f}".format),
            f"Median (s) HEAD {new_commit}": merged["median_new"].map("{:.5f}".format),
            "Median Change": pct_change.map("{:+.2f}%".format),
            f"Mean ± SD (s) BASE {old_commit}": [
                _fmt(m, s)
                for m, s in zip(merged["mean_old"], merged["stddev_old"], strict=True)
            ],
            f"Mean ± SD (s) HEAD {new_commit}": [
                _fmt(m, s)
                for m, s in zip(merged["mean_new"], merged["stddev_new"], strict=True)
            ],
        }
    )

    # disable_numparse: keep our fixed-precision strings exactly (tabulate otherwise
    # re-parses numeric-looking cells and strips trailing zeros, so medians would show
    # inconsistent precision next to the mean ± SD column).
    report = df.to_markdown(index=False, disable_numparse=True)
    if header:
        report = f"## {header}\n\n{report}"
    _write(out_file, report)

    # Fail if any benchmark's median regressed beyond threshold
    if (pct_change > REGRESSION_THRESHOLD).any():
        print(  # noqa: T201
            f"\nFAILED: median regression exceeds {REGRESSION_THRESHOLD}% threshold"
        )
        sys.exit(1)


if __name__ == "__main__":
    header = sys.argv[4] if len(sys.argv) > 4 else None
    make_report(sys.argv[1], sys.argv[2], sys.argv[3], header)
