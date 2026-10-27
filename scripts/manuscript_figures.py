"""Publication-width figures from the unchanged audited final-validation CSVs."""
from __future__ import annotations

import csv
import statistics
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

METHODS = {
    "reactive_carbon": "Reactive",
    "equal_split": "Equal split",
    "service_first_gnn": "Single / GNN",
    "multipath_carbon_gnn": "Multipath / GNN",
    "multipath_carbon_persistence": "Multipath / persistence",
    "perfect_multipath_carbon": "Perfect demand",
}


def load(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def service(rows: list[dict[str, str]]) -> float:
    return 100*sum(float(r["served_mb"]) for r in rows)/sum(float(r["offered_mb"]) for r in rows)


def render(root: Path, folder: Path) -> None:
    evidence = root / "results/final-validation-20261027"
    rows = load(evidence / "summary.csv")
    metrics = load(evidence / "forecast_metrics.csv")
    proof = root / ".scratch/paper-proof"
    proof.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
                         "pdf.fonttype": 42})

    def save(fig, stem):
        fig.savefig(folder / "images" / f"{stem}.pdf", bbox_inches="tight")
        fig.savefig(proof / f"{stem}.png", dpi=170, bbox_inches="tight")
        plt.close(fig)

    # One IEEE column: stack networks so 9 pt labels retain their printed size.
    fig, axes = plt.subplots(2, 1, figsize=(3.5, 3.8))
    for ax, network in zip(axes, ("geant", "abilene")):
        for x, kind in enumerate(("gnn", "gru", "persistence")):
            selected = [r for r in metrics if r["network"] == network and r["model"] == kind]
            seeds = sorted({r["model_seed"] for r in selected})
            values = [statistics.mean(float(r["mae_mbps"]) for r in selected if r["model_seed"] == seed) for seed in seeds]
            ax.bar(x, statistics.mean(values), color=("#4b74d8", "#159c92", "#a3a6ad")[x], alpha=.8)
            if len(values) > 1:
                ax.errorbar(x, statistics.mean(values), yerr=statistics.stdev(values), capsize=3, color="black")
                ax.scatter([x-.08, x, x+.08], values, s=13, color="black", zorder=3)
        ax.set_xticks(range(3), ("GNN", "GRU", "Persistence"))
        ax.set_title("GÉANT" if network == "geant" else "Abilene")
        ax.set_ylabel("Three-horizon MAE (Mbps)")
    fig.tight_layout()
    save(fig, "seed_forecast_error")

    causal = [r for r in rows if r["scenario"] == "congested" and r["model_seed"] in ("-1", "42")]

    def select(network, factor, policy):
        return [r for r in causal if r["network"] == network and int(r["capacity_factor"]) == factor and r["policy"] == policy]

    fig, axes = plt.subplots(1, 2, figsize=(6.5, 3.35))
    for ax, network in zip(axes, ("geant", "abilene")):
        for policy, label in METHODS.items():
            ax.plot((10, 20, 40), [service(select(network, f, policy)) for f in (1, 2, 4)],
                    marker="o", markersize=3.5, label=label,
                    linestyle="--" if policy.startswith("perfect") else "-")
        ax.set_title("GÉANT" if network == "geant" else "Abilene")
        ax.set_xticks((10, 20, 40))
        ax.set_xlabel("Assumed capacity (Mbps)")
        ax.set_ylabel("Pooled demand served (%)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, ncol=3, loc="lower center", fontsize=7.5)
    fig.tight_layout(rect=(0, .18, 1, 1))
    save(fig, "capacity_sensitivity")

    fig, axes = plt.subplots(3, 2, figsize=(6.5, 7.05))
    for r, factor in enumerate((1, 2, 4)):
        for c, network in enumerate(("geant", "abilene")):
            ax = axes[r, c]
            for j, (policy, label) in enumerate(METHODS.items()):
                selected = select(network, factor, policy)
                ax.scatter(service(selected), statistics.mean(float(v["forwarding_score"]) for v in selected),
                           marker=("o", "s", "^", "D", "v", "X")[j], s=32, label=label)
            ax.set_title(("GÉANT" if network == "geant" else "Abilene")+f" / {10*factor} Mbps")
            ax.set_xlabel("Pooled demand served (%)")
            ax.set_ylabel("Forwarding score")
            ax.tick_params(labelsize=8)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, ncol=3, loc="lower center", fontsize=7.5)
    fig.tight_layout(rect=(0, .075, 1, 1), h_pad=1.25)
    save(fig, "carbon_service_tradeoffs")
