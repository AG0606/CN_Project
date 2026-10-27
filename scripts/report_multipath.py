"""Generate a complete, explicitly simulated multipath findings report."""
import argparse
from pathlib import Path

import pandas as pd

from carbonroute.common import load_json, sha256


def report(folder: Path) -> None:
    manifest = load_json(folder / "manifest.json")
    if manifest["status"] != "complete" or sha256(folder / "summary.csv") != manifest["summary_sha256"]:
        raise ValueError("Incomplete or changed study")
    frame = pd.read_csv(folder / "summary.csv")
    lines = ["# Fractional multipath routing: matched later-period comparison", "",
             "Every declared method is reported. The protocol, original model hashes, verified input hashes "
             "and scientific source hashes were frozen locally before routing outcomes. This is not an external "
             "preregistration. No neural model was retrained; GNN and persistence use the original checkpoints "
             "and original validation margins.", "",
             "## Source-availability preflight", "",
             "The first proposed GÉANT period (22–28 July) failed the native-source availability rule with 132 "
             "empty demand sections. No routing results were produced for that attempt. The first consecutive "
             "seven-day period on/after 22 July with nonempty demand sections and a complete initial three-hour "
             "lookback starts on 26 July; it was selected using availability only. The failed protocol and screen "
             "are retained in ../multipath-20261027/. A nonempty source section does not prove complete or "
             "accurate traffic; individual unlisted OD demands still follow the original zero rule.", "",
             "## Method and comparison contract", "",
             "The LP conserves 100% of each predicted OD aggregate over the same delay-bounded candidate paths. "
             "It minimizes maximum link utilization for the per-OD maximum over three forecast horizons. "
             "Carbon mode then minimizes offered-traffic-weighted path carbon with peak utilization limited to "
             "max(0.8, the minimum achievable envelope peak). TE mode retains the minimum peak and has no carbon "
             "objective. Thus the TE/carbon comparison includes an explicit 80% planning-headroom tradeoff, "
             "not a promise of simultaneous minimum carbon and minimum utilization. A final LP minimizes "
             "L1 changes in path fractions. The quantized variant rounds to 100 buckets per OD and reports "
             "post-rounding planning-guard violations.", "",
             "Actual current demand is revealed only after fractions are committed. The same equal-rate max-min "
             "allocator serves whole OD aggregates using fractional link incidence; subpaths never earn extra "
             "fairness shares. One-hot routing matches the original single-path allocator and is checked during "
             "replay. Offered utilization includes ALL offered bytes, including traffic that cannot be served; "
             "the optimizer cannot invent savings by admitting less traffic before overload accounting.", "",
             "This is an ideal aggregate fractional model. It does not demonstrate switch configuration, "
             "flow hashing, packet ordering, TCP goodput or measured packet latency. The rounded variant "
             "tests finite weights only; it does not prove practical flow-level realizability. Paths may "
             "share bottlenecks, and no split can increase those physical cut capacities.", "",
             "GÉANT pairs 2005 traffic with 2022 daily country carbon. Abilene uses fixed 2004 annual EPA "
             "regional rates. Carbon scores and carbon-weighted bytes are forwarding attribution proxies, "
             "not measured emissions. Selected flows, fixed assumed capacities, training-only traffic scaling, "
             "one existing model seed and seven adjacent days limit the conclusions.", "",
             "## Metrics", "",
             "Service pools served bytes / offered bytes across seven days. Carbon score, worst-pair service, "
             "overload minutes, active paths, changed OD aggregates and solver time are arithmetic daily means. "
             "A changed pair counts once even when several path weights change; redistributed mass is half "
             "the L1 weight change summed over pairs and intervals. Many tiny LP changes can increase changed-pair "
             "counts, so read them alongside redistributed mass. Undefined carbon days are counted explicitly. "
             "Absolute carbon-weighted bytes and served bytes remain in summary.csv so score reductions "
             "can be assessed alongside service and traffic mix.", ""]
    for name in ("geant", "abilene"):
        lines += [f"## {name.upper()}", "", "Replay days: "+", ".join(manifest["networks"][name]["days"])+".", ""]
        for scenario in ("normal", "congested", "bursty"):
            lines += [f"### {scenario.title()}", "",
                      "| Policy | Carbon score ↓ | Score days | Pooled served % ↑ | Worst pair % ↑ | Overload min/day ↓ | Changed pairs/day | Redistributed mass/day | Paths/pair | Decision ms |",
                      "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
            group = frame[(frame.network == name) & (frame.scenario == scenario)]
            for policy, rows in group.groupby("policy", sort=False):
                offered = rows.offered_mb.sum()
                service = 100*rows.served_mb.sum()/offered if offered else float("nan")
                lines.append(f"| {policy} | {rows.forwarding_score.mean():.2f} | {rows.forwarding_score.count()}/{len(rows)} | "
                             f"{service:.3f} | {100*rows.min_pair_service_fraction.mean():.3f} | "
                             f"{rows.overload_minutes.mean():.2f} | {rows.route_changes.mean():.2f} | "
                             f"{rows.redistributed_mass.mean():.3f} | {rows.mean_active_paths_per_pair.mean():.2f} | "
                             f"{rows.decision_ms_mean.mean():.2f} |")
            quantized = group[group.policy == "multipath_carbon_gnn_quantized"]
            lines += ["", f"Quantized planning-guard violations: {int(quantized.post_quantization_peak_violations.sum())} "
                      f"out of {int(quantized.bins.sum())} replay bins. These are forecast-envelope checks, not actual overload counts.", ""]
    lines += ["## Uncertainty and interpretation", "",
              "Paired daily differences and descriptive day-bootstrap intervals are saved. Carbon intervals "
              "use only days with defined paired scores. Served-fraction intervals concern the arithmetic "
              "mean of daily fractions, not the pooled-byte percentage above. Few adjacent days, one training "
              "seed and multiple comparisons do not establish broad statistical generalization. Compare "
              "against the matched no-carbon and persistence methods before attributing any gain to the "
              "carbon objective or GNN. All previous evaluated periods remain inspected; changes informed "
              "by this study require another protocol and new evaluation, not silent replacement of these results.", ""]
    (folder / "FINDINGS.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved {folder / 'FINDINGS.md'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    args = parser.parse_args()
    report(args.folder.resolve())
