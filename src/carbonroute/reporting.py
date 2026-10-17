"""Offline, self-contained replay report and publication-friendly plot exports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .common import load_json, sha256

LABELS = {"shortest_path": "Shortest path", "reactive_carbon": "Reactive carbon",
          "predictive_te": "Predictive TE", "predictive_carbon": "GNN + safeguards",
          "persistence_carbon": "Persistence + safeguards", "no_margin": "GNN without margin",
          "no_hysteresis": "GNN without hysteresis"}
COLORS = ["#7e8796", "#e39b36", "#6875d9", "#168a78", "#cb74a7", "#d96757", "#5d9eb8"]


def plot_results(root: Path, output: Path, frame: pd.DataFrame, runs: dict[str, Any]) -> None:
    figures = output / "figures"
    figures.mkdir(exist_ok=True)
    plt.rcParams.update({"font.size": 10, "figure.dpi": 130, "savefig.bbox": "tight",
                         "axes.spines.top": False, "axes.spines.right": False})
    errors = pd.read_csv(output / "forecast_metrics.csv")
    fig, ax = plt.subplots(figsize=(7, 4))
    for name, group in errors[errors.split == "test"].groupby("model"):
        ax.plot(group.horizon_bins*15, group.mae_mbps, "o-", label=name.upper())
    ax.set(xlabel="Forecast horizon (minutes)", ylabel="Held-out MAE (Mbps)",
           title="Demand prediction on active OD pairs")
    ax.set_xticks([15, 30, 45])
    ax.legend()
    fig.savefig(figures / "forecast_errors.png")
    fig.savefig(figures / "forecast_errors.pdf")
    plt.close(fig)
    delayed = frame[frame.observation_delay_bins == 1]
    summary = delayed.groupby("policy").agg(
        forwarding_score=("forwarding_score", "mean"), overload_minutes=("overload_minutes", "mean"),
        served_fraction=("served_fraction", "mean"), route_changes=("route_changes", "mean"))
    fig, ax = plt.subplots(figsize=(9, 5))
    for i, (policy, label) in enumerate(LABELS.items()):
        if policy in summary.index:
            row = summary.loc[policy]
            ax.scatter(row.forwarding_score, row.overload_minutes, s=90,
                       color=COLORS[i], label=f"{label} ({row.served_fraction:.1%} served)")
    ax.set(xlabel="Mean carbon-weighted forwarding score (sum of hop CI)",
           ylabel="Mean overload minutes per day", title="Routing trade-off • one-bin observation lag")
    ax.legend(loc="center left", bbox_to_anchor=(1, .5), frameon=False)
    fig.savefig(figures / "carbon_overload_tradeoff.png")
    fig.savefig(figures / "carbon_overload_tradeoff.pdf")
    plt.close(fig)
    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    for i, policy in enumerate(list(LABELS)[:4]):
        matched = [r for r in runs.values() if r["summary"]["policy"] == policy
                   and r["summary"]["scenario"] == "congested" and r["summary"]["observation_delay_bins"] == 1]
        if not matched:
            continue
        records = matched[0]["records"]
        x = np.arange(len(records))/4
        axes[0].plot(x, [max(r["link_utilization"]) for r in records], label=LABELS[policy], color=COLORS[i])
        axes[1].plot(x, np.cumsum([r["changes"] for r in records]), color=COLORS[i])
    axes[0].axhline(1, color="black", linestyle="--", linewidth=.8)
    axes[0].set(ylabel="Maximum offered link utilization", title="First held-out congested day • same workload")
    axes[0].legend(ncol=2)
    axes[1].set(xlabel="Scenario hours", ylabel="Cumulative route changes")
    fig.savefig(figures / "utilization_and_changes.png")
    fig.savefig(figures / "utilization_and_changes.pdf")
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    ordered = summary.reindex([p for p in LABELS if p in summary.index])
    bars = np.arange(len(ordered))
    labels = [LABELS[p].replace(" ", "\n", 1) for p in ordered.index]
    axes[0].bar(bars, ordered.served_fraction*100, color=COLORS[:len(bars)])
    axes[0].set(ylabel="Mean served demand (%)", ylim=(0, 105), title="Service must accompany carbon attribution")
    axes[1].bar(bars, ordered.route_changes, color=COLORS[:len(bars)])
    axes[1].set(ylabel="Mean route changes / day", title="Component comparisons")
    for ax in axes:
        ax.set_xticks(bars, labels, rotation=35, ha="right", fontsize=8)
    fig.tight_layout()
    fig.savefig(figures / "components.png")
    fig.savefig(figures / "components.pdf")
    plt.close(fig)


def report(root: Path, output: Path) -> Path:
    manifest = load_json(output / "manifest.json")
    if manifest.get("status") != "complete":
        raise ValueError("Only completed campaigns can be reported")
    for name in ("summary.csv", "forecast_metrics.csv", "training_summary.json"):
        if sha256(output / name) != manifest[name.split(".")[0]+"_sha256"]:
            raise ValueError(f"Campaign evidence changed: {name}")
    frame = pd.read_csv(output / "summary.csv")
    errors = pd.read_csv(output / "forecast_metrics.csv")
    # Embed only the first workload day/year's traces; all run logs remain on disk.
    first_year = int(frame.carbon_year.min())
    selected = frame[(frame.window == 0) & (frame.carbon_year == first_year)]
    runs = {row.run_id: load_json(output / "runs" / f"{row.run_id}.json") for row in selected.itertuples()}
    payload = {"manifest": manifest, "summary": json.loads(frame.to_json(orient="records")),
               "forecast": json.loads(errors.to_json(orient="records")), "runs": runs,
               "labels": LABELS, "training": load_json(output / "training_summary.json"),
               "alignments": {str(year): load_json(output / f"alignment_{year}.json")
                              for year in frame.carbon_year.unique()}}
    template = Path(__file__).with_name("report.html").read_text(encoding="utf-8")
    # Prevent any source field from breaking out of the embedded JSON script.
    embedded = json.dumps(payload, separators=(",", ":"), allow_nan=False).replace("<", "\\u003c")
    path = output / "index.html"
    path.write_text(template.replace("__DATA__", embedded), encoding="utf-8")
    plot_results(root, output, frame, runs)
    write_findings(root, output, frame, errors, manifest)
    print(f"Offline report: {path}", flush=True)
    return path


def write_findings(root: Path, output: Path, frame: pd.DataFrame, errors: pd.DataFrame,
                   manifest: dict[str, Any]) -> None:
    mean_errors = errors[errors.split == "test"].groupby("model").mae_mbps.mean()
    rows = ["# Measured results and interpretation", "",
            f"Generated from {len(frame)} successful paired runs; {len(manifest['failed_runs'])} failures.", "",
            "## Forecast accuracy", "", "Mean MAE over the three horizons, active pairs only:", ""]
    rows += [f"- {kind}: {value:.4f} Mbps." for kind, value in mean_errors.items()]
    if mean_errors.gnn >= mean_errors.persistence:
        rows += ["", "The GNN does **not** beat persistence on mean held-out MAE in this run. Do not claim otherwise."]
    if mean_errors.gnn >= mean_errors.gru:
        rows += ["", "The no-graph GRU has lower mean held-out MAE; this run does not establish a benefit from graph aggregation."]
    rows += ["", "## Routing (arithmetic mean across paired day/carbon realizations)", "",
             "| Scenario / lag | Policy | Forwarding score | Served | Overload min/day | Changes/day |",
             "|---|---|---:|---:|---:|---:|"]
    grouped = frame.groupby(["scenario", "observation_delay_bins", "policy"])
    for (scenario, lag, policy), group in grouped:
        rows.append(f"| {scenario} / {lag} | {LABELS[policy]} | {group.forwarding_score.mean():.2f} | "
                    f"{group.served_fraction.mean():.2%} | {group.overload_minutes.mean():.1f} | {group.route_changes.mean():.1f} |")
    rows += ["", "## What these results establish", "",
             "The implementation runs an actual GCN–GRU and compares causal routing policies on identical trace-derived workloads. "
             "The marginal value of the model and each safeguard must be judged from paired_differences.csv and the component rows. "
             "A lower forwarding score alone is not evidence of reduced physical network electricity use.", "",
             "## Evidence limits", "",
             "- Traffic is from 2005, paired by weekday and season with 2022–2024 carbon. These are constructed scenarios, not simultaneous observations.",
             "- Daily carbon is held constant over each day and the planning horizon. No carbon forecasting or subhourly grid observations.",
             "- Eight nodes and six training-selected directed OD pairs; configured capacities/delays, one model seed.",
             "- Aggregate max-min service, not TCP goodput, packet loss or RTT. One-bin lag means 15 scenario minutes.",
             "- Forwarding score sums sender CI over hops, weighted by served bytes. Hypothetical idle/beta models are sensitivity examples only.",
             "- The paper campaign uses five adjacent held-out days. Window-clustered bootstrap intervals are descriptive and adjacent days may still correlate.",
             "- No Mininet/OpenFlow actuation was run. Publication novelty and generalization are not established by this implementation.", "",
             "## Reproduction", "", "See manifest.json, alignment_*.json, runs/*.json, summary.csv and figures/. "
             "The manifest records input/model/config/source hashes. Repeated deterministic runs do not create additional independent evidence.", ""]
    (output / "FINDINGS.md").write_text("\n".join(rows), encoding="utf-8")
