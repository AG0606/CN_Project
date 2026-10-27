"""Generate final-check tables and scientific figures from frozen outcomes."""
import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from carbonroute.common import load_json, save_json, sha256

LABELS = {"reactive_carbon": "Reactive", "equal_split": "Equal split", "service_first_gnn": "Single / GNN",
          "multipath_carbon_gnn": "Multipath / GNN", "multipath_carbon_gru": "Multipath / GRU",
          "multipath_carbon_persistence": "Multipath / persistence", "perfect_multipath_carbon": "Perfect demand / multipath"}


def pooled(rows: pd.DataFrame) -> float:
    offered = rows.offered_mb.sum()
    return float(rows.served_mb.sum()/offered) if offered else float("nan")


def report(folder: Path) -> None:
    manifest = load_json(folder / "manifest.json")
    if manifest["status"] != "complete":
        raise ValueError("Incomplete final validation")
    for filename in ("summary.csv", "forecast_metrics.csv", "day_cluster_intervals.csv"):
        if sha256(folder / filename) != manifest[filename.removesuffix(".csv")+"_sha256"]:
            raise ValueError("Changed final outcomes")
    frame = pd.read_csv(folder / "summary.csv")
    metrics = pd.read_csv(folder / "forecast_metrics.csv")
    audit = load_json(folder / "AUDIT.json")
    if audit["summary_sha256"] != sha256(folder / "summary.csv") or audit["runs"] != len(frame):
        raise ValueError("Audit does not match final outcomes")
    # A seed contributes one mean across the three horizons, never three independent seeds.
    seed_rows = metrics.groupby(["network", "model", "model_seed"], as_index=False).mae_mbps.mean()
    seed_rows.to_csv(folder / "seed_forecast_summary.csv", index=False)
    base = frame[(frame.capacity_factor == 1) & frame.policy.isin(("service_first_gnn_no_margin", "multipath_carbon_gnn_no_margin"))]
    oracle_rows = []
    for causal, perfect in (("service_first_gnn_no_margin", "perfect_service_first"),
                            ("multipath_carbon_gnn_no_margin", "perfect_multipath_carbon")):
        diagnostic = frame[(frame.capacity_factor == 1) & (frame.policy == perfect)]
        joined = base[base.policy == causal].merge(diagnostic, on=["network", "window", "scenario"],
                                                  suffixes=("_causal", "_perfect"), validate="one_to_one")
        for row in joined.itertuples():
            oracle_rows.append({"network": row.network, "window": row.window, "scenario": row.scenario,
                                "planner": causal.removesuffix("_gnn_no_margin"),
                                "causal_score": row.forwarding_score_causal, "perfect_score": row.forwarding_score_perfect,
                                "causal_service": row.served_fraction_causal, "perfect_service": row.served_fraction_perfect,
                                "causal_overload": row.overload_minutes_causal, "perfect_overload": row.overload_minutes_perfect})
    pd.DataFrame(oracle_rows).to_csv(folder / "perfect_forecast_comparisons.csv", index=False)
    lines = ["# Final validation before paper writing", "",
             f"Independent audit passed: {audit['runs']:,} runs, {audit['bins']:,} replay intervals, "
             f"{audit['new_checkpoints']} new checkpoints, {audit['explicit_future_demand_runs']} "
             "explicitly future-aware diagnostics. See AUDIT.json.", "",
             "Three training seeds (7, 42, 123), fixed capacity scenarios (10, 20, 40 Mbps/direction), and "
             "the same planners receiving actual next-three-bin demand as explicitly future-aware diagnostics. "
             "No winning seed or scenario is selected. The protocol and evaluation plan were frozen locally; "
             "this is not an external preregistration.", "",
             "Training used only the original training/validation splits and their transforms. GÉANT uses "
             "its original 40-epoch/8-patience limit; Abilene uses 25 epochs/patience 6. The frozen protocol's "
             "narrative generalized 40/8 to both networks; PROTOCOL_ERRATUM.json documents this wording error. "
             "The code always used the correct original per-network settings, recorded in the evaluation plan "
             "and checkpoint metadata. Test data did not enter training or checkpoint selection.", "",
             "Capacity scenarios are declared assumptions, not measured historical capacities or guaranteed "
             "light/moderate/heavy regimes. Normal, scaled-congested and seeded-burst traffic is identical "
             "between every method in a paired condition. Model seed 42 is used for the capacity comparison; "
             "all three seeds are evaluated for the two primary GNN/GRU planners at reference capacity. "
             "Forecasts are cached across comparisons, so final-validation decision times exclude bulk "
             "neural forecasting and are not end-to-end deployment latency.", "",
             "Perfect-demand controls use the same algorithm and current carbon as causal controls, with "
             "the true next three demand matrices and zero margin. They are not deployable or guaranteed "
             "bounds on realized service/carbon. Zero-margin causal seed42 controls at 10 Mbps isolate "
             "forecast replacement from margin removal; higher-capacity diagnostics also remove margins "
             "and should not be interpreted as an isolated forecast-accuracy effect.", "",
             "All seven replay days are retained. Forecast metrics cover each replay-bin start, with two "
             "additional future-label bins beyond the last day; no gaps are crossed. Source availability "
             "is checked before outcomes. GÉANT uses daily 2022 country carbon with 2005 traffic; Abilene "
             "uses static annual 2004 EPA regional carbon. Scores are forwarding proxies, not measured CO₂.", "",
             "## Check 1: forecast error across training seeds", "",
             "Mean MAE across three horizons (Mbps), then mean/sample standard deviation across three "
             "training seeds. Persistence is deterministic and has no seed standard deviation. These "
             "standard deviations are not confidence intervals over independent test days.", "",
             "| Network | GNN mean ± seed SD | GRU mean ± seed SD | Persistence |",
             "| --- | ---: | ---: | ---: |"]
    for name in ("geant", "abilene"):
        selected = seed_rows[seed_rows.network == name]
        gnn, gru = selected[selected.model == "gnn"].mae_mbps, selected[selected.model == "gru"].mae_mbps
        persistence = selected[selected.model == "persistence"].mae_mbps.iloc[0]
        lines.append(f"| {name} | {gnn.mean():.5f} ± {gnn.std(ddof=1):.5f} | "
                     f"{gru.mean():.5f} ± {gru.std(ddof=1):.5f} | {persistence:.5f} |")
    lines += ["", "## Check 2: matched routing/capacity outcomes", "",
              "Service pools bytes. Carbon score, overload, worst-pair service and changes average daily runs. "
              "At reference capacity the GNN/GRU service-first and carbon-multipath rows average all three "
              "seeds; other capacities use seed42. Seed-specific rows remain in summary.csv. Reported seed "
              "counts exclude deterministic controls. Pooled percentages cannot be directly substituted "
              "for the arithmetic daily-fraction differences used in the uncertainty CSV.", ""]
    for name in ("geant", "abilene"):
        lines += [f"### {name.upper()}", "", "Replay dates: "+", ".join(manifest["networks"][name]["days"])+".", ""]
        for factor in (1, 2, 4):
            for scenario in ("normal", "congested", "bursty"):
                rows = frame[(frame.network == name) & (frame.capacity_factor == factor) & (frame.scenario == scenario)]
                lines += [f"#### {10*factor} Mbps / {scenario}", "",
                          "| Policy | Seeds | Carbon score ↓ | Pooled service % ↑ | Worst pair % ↑ | Overload min/day ↓ | Changed pairs/day |",
                          "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
                for policy, selected in rows.groupby("policy", sort=False):
                    seeds = selected[selected.model_seed >= 0].model_seed.nunique()
                    lines.append(f"| {policy} | {seeds or '—'} | {selected.forwarding_score.mean():.2f} | "
                                 f"{100*pooled(selected):.3f} | {100*selected.min_pair_service_fraction.mean():.3f} | "
                                 f"{selected.overload_minutes.mean():.2f} | {selected.route_changes.mean():.2f} |")
                lines.append("")
    lines += ["## Check 3: isolated perfect-demand comparison at reference capacity", "",
              "Both columns use zero margin, the same planner and 10 Mbps capacity. Positive or negative "
              "differences are retained; perfect demand is not guaranteed to optimize these realized metrics.", "",
              "| Network / workload / planner | Causal → perfect score | Causal → perfect pooled service % | Causal → perfect overload min/day |",
              "| --- | ---: | ---: | ---: |"]
    for name in ("geant", "abilene"):
        for scenario in ("normal", "congested", "bursty"):
            for causal, perfect in (("service_first_gnn_no_margin", "perfect_service_first"),
                                    ("multipath_carbon_gnn_no_margin", "perfect_multipath_carbon")):
                common = (frame.network == name) & (frame.scenario == scenario) & (frame.capacity_factor == 1)
                a, b = frame[common & (frame.policy == causal)], frame[common & (frame.policy == perfect)]
                lines.append(f"| {name} / {scenario} / {causal.removesuffix('_gnn_no_margin')} | "
                             f"{a.forwarding_score.mean():.2f} → {b.forwarding_score.mean():.2f} | "
                             f"{100*pooled(a):.3f} → {100*pooled(b):.3f} | "
                             f"{a.overload_minutes.mean():.2f} → {b.overload_minutes.mean():.2f} |")
    lines += ["", "## Interpretation limits", "", "Three seeds test initialization sensitivity, not "
              "universal GNN performance. Capacity sensitivity is conditional on declared scaled traffic "
              "and selected paths. Perfect-demand comparisons diagnose the existing objective and information "
              "pipeline; they do not prove an achievable improvement or a theoretical upper bound. "
              "Bootstrap day clusters average seeds within day; seven adjacent days remain seven clusters. "
              "The carbon score can change with the served traffic mix and is not a measured energy or "
              "emissions quantity. Retain these outcomes when writing or revising the paper.", ""]
    (folder / "FINDINGS.md").write_text("\n".join(lines), encoding="utf-8")
    figures = folder / "figures"
    figures.mkdir(exist_ok=True)
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.6))
    for axis, name in zip(axes, ("geant", "abilene")):
        selected = seed_rows[seed_rows.network == name]
        for j, kind in enumerate(("gnn", "gru", "persistence")):
            values = selected[selected.model == kind].mae_mbps.to_numpy()
            axis.bar(j, values.mean(), color=("#2563eb", "#0d9488", "#9ca3af")[j], alpha=.7)
            if len(values) > 1:
                axis.errorbar(j, values.mean(), yerr=values.std(ddof=1), color="black", capsize=4)
                axis.scatter(j+np.linspace(-.09, .09, len(values)), values, color="black", s=18, zorder=3)
        axis.set_xticks(range(3), ("GNN", "GRU", "Persistence"))
        axis.set_title(name.upper())
        axis.set_ylabel("Mean three-horizon MAE (Mbps)")
    fig.suptitle("Final-period forecasting: three seeds; error bars = seed SD")
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(figures / f"seed_forecast_error.{ext}", dpi=180)
    plt.close(fig)
    # Seed42 across all regimes avoids changing the seed mixture between capacity points.
    seed42 = frame[(frame.model_seed.isin((-1, 42))) & (frame.scenario == "congested")]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    methods = ("reactive_carbon", "equal_split", "service_first_gnn", "multipath_carbon_gnn", "multipath_carbon_persistence", "perfect_multipath_carbon")
    for axis, name in zip(axes, ("geant", "abilene")):
        for policy in methods:
            rows = seed42[(seed42.network == name) & (seed42.policy == policy)]
            values = [100*pooled(rows[rows.capacity_factor == factor]) for factor in (1, 2, 4)]
            axis.plot((10, 20, 40), values, marker="o", label=LABELS[policy], linestyle="--" if policy.startswith("perfect") else "-")
        axis.set_title(name.upper())
        axis.set_xlabel("Assumed directed-link capacity (Mbps)")
        axis.set_ylabel("Pooled demand served (%)")
        axis.set_xticks((10, 20, 40))
    axes[-1].legend(loc="best", fontsize=8)
    fig.suptitle("Capacity sensitivity: congested workload, seed42 and deterministic controls")
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(figures / f"capacity_sensitivity.{ext}", dpi=180)
    plt.close(fig)
    fig, axes = plt.subplots(2, 3, figsize=(12, 6.5))
    for row_index, name in enumerate(("geant", "abilene")):
        for column, factor in enumerate((1, 2, 4)):
            axis = axes[row_index, column]
            for j, policy in enumerate(methods):
                rows = seed42[(seed42.network == name) & (seed42.capacity_factor == factor) & (seed42.policy == policy)]
                axis.scatter(100*pooled(rows), rows.forwarding_score.mean(), marker=("o", "s", "^", "D", "v", "X")[j], s=45, label=LABELS[policy])
            axis.set_title(f"{name.upper()} / {10*factor} Mbps")
            axis.set_xlabel("Pooled demand served (%) ↑")
            axis.set_ylabel("Forwarding score ↓")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, fontsize=8)
    fig.suptitle("Carbon–service tradeoffs: congested workload, seed42")
    fig.tight_layout(rect=(0, .09, 1, .95))
    for ext in ("png", "pdf"):
        fig.savefig(figures / f"carbon_service_tradeoffs.{ext}", dpi=180)
    plt.close(fig)
    outputs = [folder / "FINDINGS.md", folder / "seed_forecast_summary.csv", folder / "perfect_forecast_comparisons.csv", *figures.glob("*")]
    save_json(folder / "derived_artifacts.json", {str(path.relative_to(folder)): sha256(path) for path in outputs})
    print(f"Report and figures saved to {folder}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    args = parser.parse_args()
    report(args.folder.resolve())
