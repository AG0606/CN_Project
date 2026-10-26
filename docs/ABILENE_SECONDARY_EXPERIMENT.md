# Abilene + EPA eGRID2004: secondary US experiment

This is the intra-country companion to the main GÉANT experiment. It uses **NetFlow-derived Abilene origin–destination (OD) traffic estimates** from 2004 and **EPA eGRID2004 annual regional generation CO₂ output rates**. It uses no paid API and does not generate the base OD trace. It is an offline simulation, not a Mininet or live-SDN measurement.

## What is real, and what is assumed

| Component | Choice and provenance |
| --- | --- |
| Traffic | Original [Abilene trace collector](https://www.cs.utexas.edu/~yzhang/research/AbileneTM/readme.txt), `X01.gz`–`X04.gz`; `realOD` is the first of five values for each OD pair. These are NetFlow-derived estimates based on sampling and egress inference, not ground-truth packet counts. |
| Traffic time | Four non-contiguous weeks starting 1 March, 8 March, 2 April, and 9 April **2004**. Each file has 2016 five-minute matrices. No gap is interpolated; forecasts and replays stay inside contiguous weeks. The trace does not specify a time zone. |
| Topology | All **12 routers and 15 undirected links** from the trace's 2004 routing matrix `A`. The [Topology Zoo Abilene graph](https://github.com/mroughan/InternetTopologyZoo/blob/main/graphml/Abilene.graphml) is used only for city coordinates. Its later snapshot has 11 nodes; we restore the trace's extra `ATLA-M5` node at Atlanta's coordinates. The other 14 links match. |
| Carbon | [EPA eGRID historical archive](https://www.epa.gov/egrid/historical-egrid-data), workbook `eGRID2004_aggregation.xls`, sheet `EGRDSRL04`, `SUBRGN` and `SRCO2RTA`. The latter is the **2004 annual average** CO₂ generation output rate in lb/MWh. We multiply by 0.45359237 to obtain g/kWh. |
| Site-to-carbon join | Approximate city-to-eGRID-subregion assignments, documented below. A city coordinate is not a verified router power-meter location or exact utility service boundary. |
| Link model | 10 Mbps capacity on every directed link, 1.3 fiber stretch, 0.15 ms router delay. These are **simulation assumptions**, not published Abilene link specifications. Six OD pairs are selected using training data only; their rates are uniformly multiplied by **0.0215544** so the training shortest-path link-load p95 equals 70% of the assumed capacity. Thus load levels and congestion are constructed scenarios. |

The source archive, spreadsheets, and traffic files live in ignored `inputs/raw/`. The prepared matrices live in ignored `inputs/processed/abilene/`. Source URLs, byte counts, and SHA-256 hashes are saved in the local preparation manifest. The original files are not redistributed by the repository.

### City-to-subregion mapping

| Router(s) | City | eGRID2004 subregion | Annual rate, g CO₂/kWh |
| --- | --- | --- | ---: |
| ATLA-M5, ATLAng | Atlanta | SRSO | 676.020 |
| CHINng, IPLSng | Chicago, Indianapolis | RFCW | 705.966 |
| DNVRng | Denver | RMPA | 923.429 |
| HSTNng | Houston | ERCT | 644.355 |
| KSCYng | Kansas City | SRMW | 836.580 |
| LOSAng, SNVAng | Los Angeles, Sunnyvale | CAMX | 398.575 |
| NYCMng | New York City | NYCW | 418.312 |
| STTLng | Seattle | NWPP | 417.806 |
| WASHng | Washington DC | RFCE | 496.925 |

This lookup is an approximate reading of the EPA eGRID2004 subregion map in the historical technical-support document. EPA cautions that [eGRID subregions](https://www.epa.gov/egrid/frequent-questions-about-egrid) are not exact electricity-consumption boundaries. In particular, the assignment does **not** identify the actual generation mix supplying a router. Every router's rate is constant across all five-minute steps. The experiment can test whether routing reacts to **geographic** differences in a same-year carbon-rate scenario; it cannot test response to **hourly** changes in grid emissions.

Here, “reactive carbon” means the existing carbon-aware policy uses the most recently observed traffic and current (fixed annual) regional rates. Its route changes arise from traffic and capacity conditions, **not** from changing EPA carbon values.

## Reproduce on Windows

From the repository root, after the existing `SETUP.ps1` environment setup:

```powershell
.\.venv\Scripts\python.exe -m carbonroute.abilene prepare
.\.venv\Scripts\python.exe -m carbonroute.abilene train
.\.venv\Scripts\python.exe -m carbonroute.abilene run
.\.venv\Scripts\python.exe -m carbonroute.abilene report
.\.venv\Scripts\python.exe scripts/verify_abilene.py
```

The first preparation downloads four Abilene weeks (~29 MB) and the EPA historical archive (~157 MB); it then extracts the 2004 workbook. Training and replay use CPU only. `run --overwrite` regenerates an existing result. The self-contained [dashboard](../results/demo/index.html) has GÉANT and Abilene tabs; the Abilene CLI `report` command refreshes that one file. No Linux VM or Mininet is required for this secondary experiment. Keep the GÉANT pipeline and its checkpoints separate.

The code is in `src/carbonroute/abilene.py`; the configuration is `configs/abilene.json`. Network/model/replay code is shared with GÉANT after generalizing from eight to twelve nodes and from 15-minute to five-minute bins. Abilene models are retrained under `artifacts/abilene/`. The test week is untouched during model selection: X01–X02 are training, X03 is validation, and X04 is test. Two complete days from X04 are used for the paired replay; each has normal, congested, and bursty demand scenarios. The same realized traffic and annual carbon vector are fed to all seven policies in each case. The 42 per-policy run logs and source checks are verified by `scripts/verify_abilene.py`.

## Pilot findings, with limits

Means below cover **two held-out days × three scenarios**, six paired cases per policy. The carbon score is the sum of served megabytes weighted by the annual regional rate at each forwarding sender, divided by total served megabytes. It has units of carbon-intensity-weighted forwarding hops and is **not grams of CO₂** or measured device electricity. Lower is preferable only when read alongside service and utilization. The model's hypothetical power sensitivities are separate from this score.

| Policy | Carbon score ↓ | Served fraction ↑ | Overload minutes ↓ | p95 link utilization ↓ | Route changes ↓ |
| --- | ---: | ---: | ---: | ---: | ---: |
| Shortest path | 1605.452 | ~100% | 0.833 | 35.5% | 0.0 |
| Reactive carbon | 1566.072 | ~100% | 0.833 | 36.0% | 5.5 |
| Predictive TE | 1988.233 | ~100% | 0.833 | 29.9% | 29.7 |
| GNN + safeguards | 1567.678 | ~100% | 0.833 | 35.9% | 5.7 |
| Persistence + safeguards | 1567.883 | ~100% | 0.833 | 35.9% | 5.7 |
| GNN without margin | 1566.072 | ~100% | 0.833 | 36.0% | 5.5 |
| GNN without hysteresis | 1555.842 | ~100% | 0.833 | 37.3% | 8.3 |

Reactive carbon lowers this proxy by about **2.45%** versus shortest path on the paired cases. The safeguarded GNN policy is about **0.10% higher** than reactive carbon; it **does not improve the carbon score** in this pilot. Removing hysteresis lowers the score by about 0.65% versus reactive carbon but increases route changes. Predictive traffic engineering has the lowest p95 utilization and a substantially higher carbon score. Served fractions round to 100%, but there is a small amount of capacity-limited service in congested cases, so inspect exact `summary.csv` values rather than treating the rounded figure as perfect service. Overload minutes measure bins where **offered** link load exceeds the assumed 10 Mbps capacity; they do not mean packet-level latency was measured.

On the test week, horizon-1 GNN traffic MAE is **0.1701 Mbps**, essentially identical to persistence (**0.1701 Mbps**); the no-graph GRU is **0.1711 Mbps**. At three steps, GNN MAE is **0.2687 Mbps**, persistence **0.2689 Mbps**, and GRU **0.2618 Mbps**. These results do not establish an advantage for graph forecasting on this selected subset. With only two test-day clusters, any intervals in `paired_differences.csv` are descriptive and should not be used as publication-level significance claims.

The result supports a modest methods claim: the same routing framework can be evaluated on a same-year, intra-country trace with real OD estimates and independently sourced subnational annual carbon rates. It does **not** validate time-varying carbon prediction, actual emissions savings, or superiority of the GNN over reactive routing. A stronger paper will need more held-out weeks, independently justified capacity assumptions, and preferably timestamped regional carbon data if temporal carbon response is claimed.
