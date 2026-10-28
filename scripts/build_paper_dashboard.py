"""Build the existing dashboard design using only the audited final-paper results."""
from __future__ import annotations

import base64
import json
import re
import zlib
from pathlib import Path

import pandas as pd

from carbonroute.common import load_json, sha256

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "results/final-validation-20261027"
OUTPUT = FOLDER / "dashboard.html"
LABELS = {
    "shortest_path": "Shortest path", "reactive_carbon": "Reactive carbon",
    "equal_split": "Equal split", "service_first_gnn": "Service-first / GNN",
    "service_first_gru": "Service-first / GRU",
    "service_first_persistence": "Service-first / persistence",
    "multipath_carbon_gnn": "Carbon multipath / GNN",
    "multipath_carbon_gru": "Carbon multipath / GRU",
    "multipath_carbon_persistence": "Carbon multipath / persistence",
    "multipath_te_gnn": "Multipath TE / GNN / no carbon",
}


def build() -> Path:
    manifest, audit = load_json(FOLDER / "manifest.json"), load_json(FOLDER / "AUDIT.json")
    assert manifest["status"] == "complete"
    for filename in ("summary.csv", "forecast_metrics.csv", "day_cluster_intervals.csv"):
        assert sha256(FOLDER / filename) == manifest[filename[:-4]+"_sha256"]
    frame = pd.read_csv(FOLDER / "summary.csv")
    assert audit["summary_sha256"] == sha256(FOLDER / "summary.csv")
    assert audit["runs"] == len(frame) == 2058
    forecasts = pd.read_csv(FOLDER / "forecast_metrics.csv")
    entries = {item["run_id"]: item for item in manifest["runs"]}
    payload = {"labels": LABELS, "audit": audit, "summary_sha256": audit["summary_sha256"]}
    replay_count = 0
    fields = ("traffic_time", "observed_through", "carbon", "offered_mbps", "served_mbps",
              "path_fractions", "link_utilization")
    for network, old_folder in (("geant", "demo"), ("abilene", "abilene")):
        old = load_json(ROOT / "results" / old_folder / "manifest.json")
        final = manifest["networks"][network]
        # Only static graph metadata is reused, never old campaign outcomes.
        assert old["graph_hash"] == final["graph_hash"]
        graph = old["graph"]
        runs = {}
        selected = frame[(frame.network == network) & (frame.window == 0)
                         & frame.model_seed.isin((-1, 42)) & frame.policy.isin(LABELS)]
        for row in selected.itertuples():
            run_id = (f"{network}_d0_{row.scenario}_c{row.capacity_factor}_"
                      f"{row.policy}_s{row.model_seed}")
            entry = entries[run_id]
            path = (FOLDER / entry["file"]).resolve()
            assert path.is_relative_to((FOLDER / "runs").resolve())
            assert sha256(path) == entry["sha256"]
            original = load_json(path)
            replay = {"summary": original["summary"], "candidate_routes": original["candidate_routes"],
                      "path_owners": original["path_owners"],
                      "records": [{key: record[key] for key in fields}
                                  for record in original["records"]]}
            runs[f"{row.scenario}_{row.capacity_mbps:g}_{row.policy}"] = base64.b64encode(
                zlib.compress(json.dumps(replay, separators=(",", ":"), allow_nan=False).encode(), 9)
            ).decode()
            replay_count += 1
        subset = frame[frame.network == network]
        forecast = forecasts[forecasts.network == network]
        payload[network] = {
            "summary": json.loads(subset.to_json(orient="records", double_precision=15)),
            "forecast": json.loads(forecast.to_json(orient="records", double_precision=15)),
            "runs": runs, "days": final["days"],
            "manifest": {"config": final["config"], "graph": graph,
                         "traffic_manifest": {"pairs": old["traffic_manifest"]["pairs"]}},
            "alignments": {"2022": load_json(FOLDER / "geant_alignment.json")} if network == "geant" else {},
        }
    assert replay_count == 180
    # Regression anchors are the manuscript's rounded Tables 2, 3 and 4 values.
    def aggregate(network, policy, capacity, seeds):
        rows = frame[(frame.network == network) & (frame.policy == policy)
                     & (frame.scenario == "congested") & (frame.capacity_mbps == capacity)
                     & frame.model_seed.isin(seeds)]
        return 100*rows.served_mb.sum()/rows.offered_mb.sum(), rows.forwarding_score.mean()
    assert tuple(round(x, n) for x, n in zip(aggregate("geant", "multipath_carbon_gnn", 10, (7, 42, 123)), (3, 2))) == (25.254, 528.02)
    assert tuple(round(x, n) for x, n in zip(aggregate("geant", "multipath_carbon_gnn", 40, (42,)), (3, 2))) == (80.412, 371.35)
    assert tuple(round(x, n) for x, n in zip(aggregate("abilene", "multipath_carbon_gnn", 10, (7, 42, 123)), (3, 2))) == (76.189, 1888.94)
    template = (ROOT / "src/carbonroute/combined_dashboard.html").read_text(encoding="utf-8")
    legacy = template.split("<script>\n", 1)[1].split("</script>", 1)[0]
    render = legacy[legacy.index("function render(){"):legacy.index("function forecast(){")]
    render = render.replace("function render(){", "function renderReplay(){")
    render = render.replace("const k=Number($('step').value),r=selectedRun.records[k],f=Number($('flow').value),route=r.routes[f],", "const k=Number($('step').value),r=selectedRun.records[k],f=Number($('flow').value),parts=selectedRun.candidate_routes.map((nodes,i)=>({nodes,w:r.path_fractions[i],owner:selectedRun.path_owners[i]})).filter(p=>p.owner===f&&p.w>1e-6),route=[...new Set(parts.flatMap(p=>p.nodes))],")
    render = render.replace("$('route-text').textContent=route.map(n=>ids[n]).join(' → ');$('reason').textContent=r.reasons[f].replaceAll('-',' ');", "$('route-text').textContent=parts.map(p=>pct(p.w,1)+' via '+p.nodes.map(n=>ids[n]).join(' → ')).join('; ');$('reason').textContent='Recorded committed path fractions · day 1 · seed 42 for neural policies';")
    render = render.replace("$('predicted').textContent=pct(r.projected_max_utilization);", "$('predicted').textContent='Not recorded';")
    render = render.replace("+' · Infeasible pairs: '+r.infeasible_pairs", "+' · Forecast peak was not retained in final replay logs'")
    render = render.replace("year+' seasonal pairing'", "'2022 daily replay'")
    render = render.replace("route.slice(0,-1).forEach((a,i)=>{const b=route[i+1]", "parts.forEach(part=>part.nodes.slice(0,-1).forEach((a,i)=>{const b=part.nodes[i+1]")
    render = render.replace('stroke="#087aaf" stroke-width="3" marker-end="url(#arrow)"/>`;});', 'stroke="#087aaf" stroke-width="${2+4*part.w}" marker-end="url(#arrow)"/>`; }));')
    script = (ROOT / "src/carbonroute/paper_dashboard.js").read_text(encoding="utf-8")
    script = script.replace("// __REPLAY_RENDER__", render)
    template = re.sub(r"<script>\n[\s\S]*?</script>", lambda _: "<script>\n"+script+"\n</script>", template, count=1)
    replacements = {
        "Trace-driven research demo": "Audited final-paper results",
        "Explore two network case studies with the same routing methods: a European GÉANT subgraph and the US Abilene backbone.": "The paper’s final evaluation: 2,058 audited runs, seven later test days per network, and 10 / 20 / 40 Mbps capacities. All displayed outcomes come from that evaluation.",
        '<label>Observation lag<select id="lag"></select></label>': '<label>Link capacity<select id="capacity"></select></label><label>Results view<select id="view"><option value="paper3">Table 3 · three seeds at 10 Mbps</option><option value="paper4">Table 4 · seed 42</option></select></label>',
        "OFFLINE · HISTORICAL INPUTS": "FINAL PAPER · AUDITED",
        "Aggregate max-min service model": "Pooled served / offered bytes · seven days",
        "Minutes / 24-hour scenario": "Mean minutes per day · seven days",
        "Per selected day; all active flows": "Mean changed OD pairs per day",
        "Same inputs. Different decisions.": "Paper results · matched routing comparison",
        "Arithmetic means across runs in the selected workload and lag. Carbon is forwarding attribution, not measured emissions. Read it alongside service.": "Served demand pools bytes; score, overload, p95 and route changes average runs. Table 3 uses three neural seeds at 10 Mbps; Table 4 fixes seed 42. Decision times exclude cached bulk inference. Carbon is a forwarding proxy, not measured emissions.",
        '<th id="h1"></th><th id="h2"></th><th id="h3"></th>': '<th id="h1"></th><th id="h2"></th><th id="h3"></th><th>Mean ± seed SD (Table 2)</th>',
        "A 90th-percentile positive validation residual supplies the margin. This is an empirical safeguard, not a formal guarantee.": "Forecasts use the final normal-traffic test period. Mean MAE spans three horizons; SD is variation over training seeds 7, 42 and 123, not a confidence interval. Validation-only margins are fixed before testing.",
    }
    for old, new in replacements.items():
        assert old in template, old
        template = template.replace(old, new)
    for marker, filename in (("__PANGOLIN_FONT__", "Pangolin-Regular-latin.woff2"),
                             ("__POPPINS_REGULAR_FONT__", "Poppins-Regular-latin.woff2"),
                             ("__POPPINS_BOLD_FONT__", "Poppins-Bold-latin.woff2")):
        template = template.replace(marker, base64.b64encode((ROOT / "assets/fonts" / filename).read_bytes()).decode())
    data = json.dumps(payload, separators=(",", ":"), allow_nan=False).replace("<", "\\u003c")
    OUTPUT.write_text(template.replace("__DATA__", data), encoding="utf-8")
    print(f"{OUTPUT}\n{len(frame):,} audited rows; {replay_count} verified first-day replays; paper regression anchors passed")
    return OUTPUT


if __name__ == "__main__":
    build()
