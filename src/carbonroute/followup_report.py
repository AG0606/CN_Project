"""Readable evidence from the fixed follow-up; retain every declared variant."""
from pathlib import Path

import pandas as pd

from .common import load_json, sha256


def report(output: Path) -> Path:
    manifest = load_json(output / "manifest.json")
    if manifest["status"] != "complete":
        raise ValueError("Follow-up campaign incomplete")
    for filename in ("summary.csv", "forecast_metrics.csv"):
        if sha256(output / filename) != manifest[filename.removesuffix(".csv") + "_sha256"]:
            raise ValueError("Changed follow-up results")
    rows = pd.read_csv(output / "summary.csv")
    forecasts = pd.read_csv(output / "forecast_metrics.csv")
    empty = rows[rows.offered_mb == 0]
    lines = ["# Later-period training and routing evaluation", "",
             "This is the first outcome evaluation on these later source periods in the recorded project experiments. "
             "The protocol, scientific code, prepared inputs and model hashes were frozen locally before final outcome evaluation. "
             "It is not an external preregistration. Training/checkpoint selection used only the declared earlier training and validation splits.", "",
             "All declared variants are reported. One seed and seven adjacent test days per network limit generalization. "
             "Carbon is a forwarding attribution proxy, not measured emissions. Capacities and scaled/bursty workloads are simulation assumptions. "
             "GÉANT traffic is paired with 2022 daily country carbon; Abilene uses fixed 2004 annual regional EPA rates.", "",
             "Variants: reference = original checkpoint; longer = original training/validation, up to 100 epochs; "
             "expanded = additional real training history and a later validation period; link_loss = same expanded data plus "
             "a 0.25-weighted shortest-path link-load error term. That term is a routing proxy, not end-to-end optimization. "
             "The original training-only pair set, rate multiplier and normalizer are fixed for every method.", ""]
    lines += ["## Outcome and source-quality warning", "",
              "Twelve new neural checkpoints were actually trained (GNN and GRU, three variants, two networks), "
              "followed by all 630 declared routing runs. Longer training, additional history and the link-load loss "
              "did not consistently improve final forecast MAE. Lower routing carbon scores cannot be attributed to a proven GNN advantage.", "",
              f"There are {len(empty)} zero-offered policy runs. Three GÉANT replay days (30 June, 1 July and 2 July 2005) "
              "have no listed demands in the native source sections; 3 July also has 43 empty fifteen-minute sections out of 96. "
              "The full forecast test split additionally includes the empty 29 June. This does not establish genuinely zero network traffic or explain the cause. "
              "The fixed parser treats unlisted demands as zero; no days were removed, filled or replaced after observing outcomes. "
              "Carbon score is undefined when no bytes are served, so it is never treated as zero or as a carbon saving.", "",
              "GÉANT's populated later days also strongly saturate the unchanged assumed capacities. This limits this comparison to a "
              "source-quality-limited stress test, not a clean confirmation of practical savings. Abilene has seven nonempty replay days, "
              "but also shows capacity pressure and mixed service/overload tradeoffs.", "",
              "Carbon columns below average defined daily scores only, with their counts shown. Service is pooled served MB / offered MB "
              "over all seven days, avoiding the misleading 100% service convention for empty days. Overload, p95 and changes remain "
              "arithmetic means over all seven daily runs. An average daily p95 is not the p95 of the pooled observations.", "",
              "See source_availability.csv and data_quality_audit.json for the post-evaluation source audit. The original frozen "
              "day_cluster_intervals.csv retains undefined GÉANT carbon differences/intervals: empty-day NaNs propagated, and its "
              "seven-cluster count includes three empty days. No GÉANT carbon confidence interval is claimed from those rows.", ""]
    for name in ("geant", "abilene"):
        network = manifest["networks"][name]
        lines += [f"## {name.upper()}", "",
                  f"Test days: {', '.join(network['days'])}.", "",
                  f"Declared chronological splits: {network['split_dates']}.", "",
                  "### Training and validation", "",
                  "| Model | Selected epoch | Validation OD MAE (Mbps) | Training seconds |",
                  "| --- | ---: | ---: | ---: |"]
        for model, info in network["predictors"].items():
            if "best_epoch" in info:
                lines.append(f"| {model} | {info['best_epoch']} | {info['validation_mae_mbps']:.5f} | {info['training_seconds']:.1f} |")
        lines += ["", "Validation values across different periods are not directly comparable; final test inputs are shared.", "",
                  "### Final forecast error", "",
                  "Forecast metrics cover all contiguous windows in the full declared test split. Routing below uses the first seven complete test days.", "",
                  "| Model | Horizon 1 MAE | Horizon 2 MAE | Horizon 3 MAE |",
                  "| --- | ---: | ---: | ---: |"]
        for model, group in forecasts[forecasts.network == name].groupby("model", sort=False):
            values = group.sort_values("horizon_bins").mae_mbps.tolist()
            lines.append(f"| {model} | " + " | ".join(f"{v:.5f}" for v in values) + " |")
        for scenario in ("normal", "congested", "bursty"):
            lines += ["", f"### Routing: {scenario}", "",
                      "All seven declared days retained; carbon uses defined days and service pools bytes. Read score alongside service and overload.", "",
                      "| Method | Carbon score | Score days | Pooled served % | Overload min/day | Mean daily p95 % | Changes/day |",
                      "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
            group = rows[(rows.network == name) & (rows.scenario == scenario)]
            for policy, cases in group.groupby("policy", sort=False):
                avg = cases[["forwarding_score", "served_fraction", "overload_minutes", "p95_utilization", "route_changes"]].mean()
                offered = cases.offered_mb.sum()
                service = 100 * cases.served_mb.sum() / offered if offered > 0 else float("nan")
                count = cases.forwarding_score.count()
                lines.append(f"| {policy} | {avg.forwarding_score:.3f} | {count}/{len(cases)} | {service:.4f} | "
                             f"{avg.overload_minutes:.2f} | {100*avg.p95_utilization:.2f} | {avg.route_changes:.2f} |")
    lines += ["", "## Interpretation rules", "",
              "The oracle sees actual current demand and has no switching penalty. It is a diagnostic and is not deployable. "
              "Its offered-demand objective is not a guaranteed lower bound on the reported served-byte daily score.", "",
              "The planner's carbon and peak guards use forecasts. Zero predicted guard violations do not guarantee actual service, overload or carbon performance. "
              "Day-cluster bootstrap intervals in day_cluster_intervals.csv are descriptive with only seven adjacent day clusters. "
              "Do not tune a method against these final outcomes and call a rerun an independent test.", ""]
    path = output / "FINDINGS.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report saved: {path}", flush=True)
    return path
