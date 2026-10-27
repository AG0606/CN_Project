"""Render the frozen service-first comparison without changing experiment evidence."""
import argparse
from pathlib import Path

import pandas as pd

from carbonroute.common import load_json, sha256


def report(folder: Path) -> None:
    manifest = load_json(folder / "manifest.json")
    if manifest["status"] != "complete" or sha256(folder / "summary.csv") != manifest["summary_sha256"]:
        raise ValueError("Incomplete or changed study")
    data = pd.read_csv(folder / "summary.csv")
    lines = ["# Service-first routing: later-period evaluation", "",
             "The protocol and scientific source hashes were frozen locally before routing outcomes. "
             "This is not an external preregistration. Every declared policy is reported, using the same "
             "historical demand, carbon, candidate paths, assumed capacities and one-bin observation delay.", "",
             "Service-first enumerates single-path assignments and applies the same max-min rate allocator "
             "to the forecast for each horizon. Assignments within 0.1% of total predicted offered demand "
             "of the best predicted served amount are eligible; among them the planner minimizes predicted "
             "served-byte carbon score, breaking ties by route changes and delay. The selected assignment "
             "is committed before current demand is revealed. This is a fixed design choice, not a guarantee "
             "about actual service or carbon.", "",
             "The GNN and persistence variants use the original trained checkpoints and their original "
             "validation margins; no new model training was performed. Carbon is a forwarding attribution "
             "proxy, not grams of measured CO₂. GÉANT traffic (2005) is paired with 2022 daily country "
             "intensities; Abilene uses 2004 annual regional rates. Assumed capacities, selected OD pairs, "
             "workload scaling, and the aggregate service model limit real-world interpretation.", "",
             "GÉANT's declared source-availability rule requires nonempty native demand sections for "
             "each replay bin and its initial lookback. A nonempty section does not establish complete or "
             "accurate traffic, and unlisted individual OD pairs remain zero under the original parser. "
             "The oracle sees current demand and is diagnostic only; it is not a bound on the reported score.", "",
             "Pooled service is total served MB divided by total offered MB. Worst-pair service is the "
             "daily minimum served/offered among active pairs, averaged over days. Carbon score, overload, "
             "changes, decision time and modeled path delay are arithmetic daily means; path delay is a "
             "propagation/router proxy, not measured packet latency. Read all metrics together.", ""]
    for name in ("geant", "abilene"):
        lines += [f"## {name.upper()}", "", "Replay days: " + ", ".join(manifest["networks"][name]["days"]) + ".", ""]
        for scenario in ("normal", "congested", "bursty"):
            lines += [f"### {scenario.title()} workload", "",
                      "| Policy | Carbon score ↓ | Pooled served % ↑ | Worst pair % ↑ | Overload min/day ↓ | Changes/day ↓ | Decision ms | Path delay ms |",
                      "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
            subset = data[(data.network == name) & (data.scenario == scenario)]
            for policy, rows in subset.groupby("policy", sort=False):
                offered = rows.offered_mb.sum()
                service = 100 * rows.served_mb.sum() / offered if offered else float("nan")
                lines.append(f"| {policy} | {rows.forwarding_score.mean():.2f} | {service:.2f} | "
                             f"{100*rows.min_pair_service_fraction.mean():.2f} | {rows.overload_minutes.mean():.2f} | "
                             f"{rows.route_changes.mean():.2f} | {rows.decision_ms_mean.mean():.2f} | "
                             f"{rows.mean_served_path_delay_ms.mean():.2f} |")
            lines.append("")
    lines += ["## Interpretation", "", "Compare service-first with both the reactive baseline and the "
              "existing joint planner, including the persistence variants. Lower carbon score can coexist "
              "with poorer service or a different traffic mix; absolute carbon-weighted bytes and all raw "
              "per-day outcomes are retained in summary.csv. Intervals in day_cluster_intervals.csv are "
              "descriptive bootstraps of only seven adjacent days, with one model seed and multiple "
              "comparisons. They are not strong evidence of generalization.", ""]
    (folder / "FINDINGS.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved {folder / 'FINDINGS.md'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    args = parser.parse_args()
    report(args.folder.resolve())
