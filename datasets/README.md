# Project datasets — open this folder for the faculty review

This folder gathers the **actual input data** for both routing experiments in one place. Start with the four CSVs in [`previews/`](previews/) if you want to show readable rows in Excel. The original downloads are in `originals/`, and the exact arrays consumed by the training/replay code are in `processed/`. [`MANIFEST.json`](MANIFEST.json) lists every file, source URL where available, size, and SHA-256 checksum.

| Study | Network/topology | OD traffic | Electricity carbon data |
| --- | --- | --- | --- |
| **GÉANT — main experiment** | [`originals/geant/geant.txt`](originals/geant/geant.txt), SNDlib native topology; the code retains eight nodes and eleven links | [`originals/geant/geant-traffic.tgz`](originals/geant/geant-traffic.tgz), 15-minute matrices from 2005 | [`originals/european-carbon/ECON-PowerCI_2015_2024.csv`](originals/european-carbon/ECON-PowerCI_2015_2024.csv), daily country estimates; the experiment uses 2022–2024 as a **cross-year scenario** |
| **Abilene — US companion** | [`originals/abilene/Abilene-A.txt`](originals/abilene/Abilene-A.txt), the trace's 2004 routing matrix; [`Abilene.graphml`](originals/abilene/Abilene.graphml) supplies city coordinates | [`X01.gz`](originals/abilene/X01.gz) through `X04.gz`, four weeks of five-minute NetFlow-derived OD estimates in 2004. The [`complete original archive`](originals/abilene/AbileneTM-all.tar) contains all 24 source weeks, although only four are used in this run | [`originals/epa/eGRID2004_aggregation.xls`](originals/epa/eGRID2004_aggregation.xls), EPA 2004 **annual** subregion generation CO₂ rates; also preserved in the [official historical ZIP](originals/epa/egrid_historical_files_1996-2016.zip) |

## Easy-to-open previews

- [`previews/geant_traffic_first_day_selected_OD.csv`](previews/geant_traffic_first_day_selected_OD.csv): one day of the six selected GÉANT OD flows, showing the **unscaled source Mbps**, not the simulated workload.
- [`previews/european_carbon_2022_sample.csv`](previews/european_carbon_2022_sample.csv): one week of original daily values for the eight retained countries.
- [`previews/abilene_traffic_first_day_selected_OD.csv`](previews/abilene_traffic_first_day_selected_OD.csv): one day of six Abilene OD flows, converted from the collector's `100 bytes/5 minutes` units to **unscaled decimal Mbps**. The four compressed source weeks and the collector's [`readme`](originals/abilene/Abilene-readme.txt) are alongside it.
- [`previews/epa2004_router_region_rates.csv`](previews/epa2004_router_region_rates.csv): the EPA annual rate assigned to each Abilene router. The source workbook's `SRCO2RTA` column is lb/MWh; multiplying by 0.45359237 gives g/kWh.

The processed `traffic.npz` files are NumPy containers holding `times`, `full_mbps`, `rates`, `mask`, and `scale`; their neighboring `manifest.json` files specify selected OD pairs, chronological splits, scaling, topology, and source hashes. `full_mbps` retains the source traffic after unit conversion; `rates` is the selected and scenario-scaled traffic used by the experiment. To inspect the archive contents without Python, use the CSV previews above.

**What the data does and does not establish:** GÉANT's 2005 traffic and 2022–2024 European carbon are deliberately paired as a scenario; they were not collected together. Abilene traffic and EPA carbon refer to the same year, but EPA's values are **annual regional averages**, fixed throughout every five-minute replay. Neither dataset measures a router's electricity use or actual network CO₂ emissions. Capacities and traffic scaling are simulation assumptions. See [`docs/DATA_SOURCES.md`](../docs/DATA_SOURCES.md) and [`docs/ABILENE_SECONDARY_EXPERIMENT.md`](../docs/ABILENE_SECONDARY_EXPERIMENT.md) for citations and methodology.

These original third-party files are available **locally for inspection**; their redistribution terms have not all been verified. `originals/`, `processed/`, and `previews/` are therefore excluded from Git. If you want the same full folder on another laptop, copy or zip `datasets/` directly; the files have real contents even when this workspace uses disk-saving hard links. Do not edit the originals in place because a hard link shares the bytes with the project's input cache. Regenerate the folder after redownloading or re-preparing data with:

```powershell
.\.venv\Scripts\python.exe scripts/build_dataset_showcase.py
```
