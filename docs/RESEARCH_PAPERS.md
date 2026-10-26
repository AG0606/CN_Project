# Research papers behind CarbonRoute

**Prepared for Review 1, 20 October 2026.** This guide separates primary research precedents from the two datasets used in the experiment. “Used” means an idea or data source informed this project; it does **not** mean we reproduced a paper's architecture, algorithm, measurements, or reported gains. The implemented method is documented in [METHODOLOGY.md](METHODOLOGY.md), [JOINT_SELECTOR.md](JOINT_SELECTOR.md), and the current code. All links below go to the author, publisher, official proceedings, or dataset provider.

## Downloaded reading copies

The following 13 PDFs are saved locally for the team to read. These are third-party papers, so `/docs/references/papers/` is ignored by Git; the source links and this guide remain shareable. Each file was checked to open as a PDF and to have the expected title on its first page. File sizes, page counts, SHA-256 checksums, and download URLs are recorded in the local [download manifest](references/papers/download_manifest.json). The SNDlib copy is the **2007 author preprint** of the later 2010 journal paper, and the RouteNet copy is an author preprint.

| Why read it | Local copy |
| --- | --- |
| GÉANT topology library | [SNDlib](references/papers/01_SNDlib_Orlowski_2007_preprint.pdf) |
| Provenance of GÉANT traffic matrices | [Uhlig et al.](references/papers/02_GEANT_Traffic_Uhlig_2006.pdf) |
| European daily grid data method | [ECON-PowerCI](references/papers/03_ECON_PowerCI_Zhang_2025.pdf) |
| Prior predictive carbon-aware routing | [CIRo](references/papers/04_CIRo_Tabaeiaghdaei_2023.pdf) |
| Predictive SDN routing | [NeuRoute](references/papers/05_NeuRoute_Azzouni_2017.pdf) |
| GNN for network modeling | [RouteNet](references/papers/06_RouteNet_Rusek_2020.pdf) |
| Centralized WAN traffic engineering | [B4](references/papers/07_B4_Jain_2013.pdf) |
| Carbon metric and power-model cautions | [CATE](references/papers/08_CATE_ElZahr_2023.pdf) |
| Graph and temporal forecasting precedent | [DCRNN](references/papers/09_DCRNN_Li_2018.pdf) |
| Future learned-adjacency idea | [Graph WaveNet](references/papers/10_Graph_WaveNet_Wu_2019.pdf) |
| SNDlib-requested dynamic-data citation | [Idzikowski et al.](references/papers/11_SNDlib_Dynamic_Energy_Idzikowski_2011.pdf) |
| Environmental routing with capacity constraints | [GreenTE](references/papers/12_GreenTE_Zhang_2010.pdf) |
| Why routing outcomes matter beyond forecast MAE | [Roughan et al.](references/papers/13_Traffic_Engineering_Estimated_Matrices_Roughan_2003.pdf) |

SNDlib also requests **Koster, Kutschka, and Raack (NGI 2010)** when citing dynamic matrices. Its [catalog BibTeX](https://sndlib.put.poznan.pl/KosterKutschkaRaack2010.bib) and [DOI](https://doi.org/10.1109/NGI.2010.5534462) are linked here; an accessible author or publisher PDF could not be verified, so there is no local copy. The actual GÉANT topology and traffic archives, and the carbon CSV, are datasets rather than papers; their download locations and checksums are in [DATA_SOURCES.md](DATA_SOURCES.md).

## The short answer for reviewers

The closest conceptual foundations are **NeuRoute** (predict demand before SDN routing), **CIRo** (carbon-aware paths can themselves use forecasts), **RouteNet/DCRNN** (graphs are useful representations for network or spatiotemporal learning), and **CATE/GreenTE** (environmental path choice must be assessed alongside capacity, delay, and an explicit power model). **B4** demonstrates centralized WAN traffic engineering. The actual network and carbon inputs come from **SNDlib/Uhlig** and **ECON-PowerCI**. Our project combines a small GCN–GRU demand forecast with validation-derived error margins and carbon-aware path selection on a trace-driven eight-node GÉANT subgraph; the joint selector searches all 64 two-path assignments for six OD pairs under a predicted carbon budget. This particular combination and its negative as well as positive results are the scoped contribution, not an invention of predictive routing, GNNs, or carbon-aware routing. [NeuRoute](https://dl.ifip.org/db/conf/cnsm/cnsm2017/1570395499.pdf), [CIRo](https://scionproto-contrib.github.io/publications/pdfs/2023/green_routing2023.pdf), [RouteNet](https://arxiv.org/abs/1910.01508), [CATE](https://doi.org/10.1145/3629165), [SNDlib](https://sndlib.put.poznan.pl/dynamicmatrices.overview.action).

## Research method precedents

### 1. NeuRoute — forecast traffic, then route in an SDN

**Azzouni, Boutaba, and Pujolle**, “NeuRoute: Predictive Dynamic Routing for Software-Defined Networks,” *CNSM*, 2017. [Official IFIP paper](https://dl.ifip.org/db/conf/cnsm/cnsm2017/1570395499.pdf).

- **Paper's point:** Its framework predicts a traffic matrix and generates dynamic forwarding decisions to improve throughput. This establishes that forecast-informed SDN routing predates our work.
- **What we used:** The forecast → route → observe loop, and the need to compare it against simpler routing. Our simulator also makes decisions from lagged demand rather than granting the policy future demand.
- **What we did not use:** NeuRoute's learned routing hyperheuristic, controller/OpenFlow implementation, reported throughput gain, or training recipe. Our route selectors are explicit optimization/heuristic code; the neural model predicts OD demand only. The present project does **not** install switch forwarding rules. [NeuRoute paper, abstract and design](https://dl.ifip.org/db/conf/cnsm/cnsm2017/1570395499.pdf).

### 2. CIRo — prior predictive carbon-aware routing

**Tabaeiaghdaei, Scherrer, Kwon, and Perrig**, “Carbon-Aware Global Routing in Path-Aware Networks,” *ACM e-Energy*, 2023, DOI [10.1145/3575813.3595192](https://doi.org/10.1145/3575813.3595192). [Author-hosted paper](https://netsec.ethz.ch/publications/papers/green_routing2023.pdf).

- **Paper's point:** CIRo forecasts and disseminates **path carbon intensity** ahead of time for endpoint path choice in the SCION/path-aware inter-domain setting. Its published system includes a carbon-intensity model, implementation, and simulation.
- **What we used:** The premise that a path can be assigned a changing carbon-related cost, and the warning that carbon-aware routing cannot be described as inherently reactive. It is a crucial related-work comparator for our novelty claim.
- **What we did not use:** CIRo's day-ahead carbon forecaster, carbon-intensity-of-data-transmission model, SCION protocol, inter-domain architecture, or physical carbon-footprint calculations. We forecast **traffic demand**, while our daily carbon series is known for the replayed day. Our byte-weighted carbon forwarding score lacks measured joules/byte and therefore is **not measured CO₂**. [CIRo, §§1, 3–4](https://scionproto-contrib.github.io/publications/pdfs/2023/green_routing2023.pdf).

### 3. RouteNet — GNNs for computer-network modeling

**Rusek, Suárez-Varela, Almasan, Barlet-Ros, and Cabellos-Aparicio**, “RouteNet: Leveraging Graph Neural Networks for Network Modeling and Optimization in SDN,” *IEEE Journal on Selected Areas in Communications* 38(10), 2260–2270, 2020, DOI [10.1109/JSAC.2020.3000405](https://doi.org/10.1109/JSAC.2020.3000405). [Author preprint](https://arxiv.org/abs/1910.01508).

- **Paper's point:** A GNN can model relationships among network paths, links, routing, and input traffic to estimate packet delay, jitter, and loss for network optimization.
- **What we used:** Motivation for graph representations in network-aware ML and for evaluating routing outcomes rather than forecast error alone.
- **What we did not use:** RouteNet's path–link message-passing architecture, its packet-performance targets, cross-topology generalization claim, or packet-level simulator. Our much smaller GCN–GRU predicts future OD **rate**, not packet delay/loss; our aggregate simulator does not measure RTT, jitter, or packet drops. [RouteNet, abstract and architecture](https://arxiv.org/abs/1910.01508).

### 4. DCRNN — graph plus temporal forecasting precedent

**Li, Yu, Shahabi, and Liu**, “Diffusion Convolutional Recurrent Neural Network: Data-Driven Traffic Forecasting,” *ICLR*, 2018. [Conference paper](https://openreview.net/pdf?id=SJiHXGWAZ).

- **Paper's point:** Combines graph-based spatial dependence and recurrent temporal learning to forecast **road** traffic; its diffusion convolution uses bidirectional random walks.
- **What we used:** General design precedent for combining graph aggregation and a recurrent time-series model, and for checking forecasts at several horizons.
- **What we did not use:** Its diffusion convolution, encoder–decoder/scheduled-sampling architecture, road datasets, or reported accuracy gains. Our fixed-adjacency GCN–GRU operates on network OD demands; the current GNN did not beat matched GRU or persistence on mean held-out MAE. [DCRNN paper](https://openreview.net/pdf?id=SJiHXGWAZ).

### 5. B4 — centralized SDN WAN traffic engineering

**Jain et al.**, “B4: Experience with a Globally-Deployed Software Defined WAN,” *ACM SIGCOMM*, 2013, DOI [10.1145/2486001.2486019](https://doi.org/10.1145/2486001.2486019). [Google-hosted paper](https://research.google.com/pubs/archive/41761.pdf).

- **Paper's point:** Reports a production Google WAN using a centralized SDN traffic-engineering service that measures demands and coordinates multipath allocation under capacity constraints.
- **What we used:** Background justification for a controller-like global view and capacity-aware WAN path planning.
- **What we did not use:** B4's OpenFlow deployment, flow splitting, production control system, or claims about production link utilization. Our current work is an offline trace-driven decision/replay system, not a deployed SDN controller. [B4 paper](https://research.google.com/pubs/archive/41761.pdf).

### 6. Carbon-aware traffic engineering and power-model caution

**El-Zahr and colleagues**, “Exploring the Benefits of Carbon-Aware Routing,” *Proceedings of the ACM on Networking* 1(CoNEXT3), article 20, 2023, DOI [10.1145/3629165](https://doi.org/10.1145/3629165). [Author paper](https://eng.ox.ac.uk/media/jwpbeeab/elzahr23benefits.pdf). The paper proposes CATE, a carbon-aware traffic-engineering heuristic that considers grid intensity, dynamic router power and powering down ports; its central message is that carbon benefit depends on the metric, traffic, topology, and equipment power behavior.

**Zhang, Yi, Liu, and Zhang**, “GreenTE: Power-aware traffic engineering,” *IEEE ICNP*, 2010, DOI [10.1109/ICNP.2010.5762751](https://doi.org/10.1109/ICNP.2010.5762751). GreenTE targets line-card energy under utilization and path-length constraints. [Publisher/author record](https://experts.arizona.edu/en/publications/greente-power-aware-traffic-engineering/).

- **What we used:** The principle of reporting an environmental objective *together with* congestion/service and path constraints. It informs why the joint selector has a carbon budget and a utilization objective and why the report discloses its assumed metric.
- **What we did not use:** CATE's or GreenTE's power model, port/line-card shutdown, optimization code, or emission-reduction claims. Our forwarding score is a comparison proxy; with no device-energy calibration, its numerical improvement cannot be called a measured CO₂ reduction. [CATE abstract and scope](https://doi.org/10.1145/3629165), [GreenTE abstract](https://experts.arizona.edu/en/publications/greente-power-aware-traffic-engineering/).

### 7. Forecast error is not the routing result

**Roughan, Thorup, and Zhang**, “Traffic Engineering with Estimated Traffic Matrices,” *ACM IMC*, 2003, DOI [10.1145/948205.948237](https://doi.org/10.1145/948205.948237). [Official conference PDF](https://conferences.sigcomm.org/imc/2003/papers/p307-roughan1.pdf).

- **Paper's point:** Studies how routing performs when optimized using imperfect traffic matrices; the size of matrix-estimation error alone need not predict traffic-engineering quality.
- **What we used:** The evaluation rule to measure **end-to-end routing behavior** as well as MAE, which is important here because GCN–GRU, GRU, and persistence are close in forecast and overload results.
- **What we did not use:** Its estimation method, topology, optimization algorithm, or numerical findings. [IMC paper](https://conferences.sigcomm.org/imc/2003/papers/p307-roughan1.pdf).

## Data and provenance papers — inputs, not copied algorithms

### 8. SNDlib and the GÉANT traffic trace

**Orlowski, Pióro, Tomaszewski, and Wessäly**, “SNDlib 1.0—Survivable Network Design Library,” *Networks* 55(3), 276–286, 2010, DOI [10.1002/net.20371](https://doi.org/10.1002/net.20371). [SNDlib's own bibliography](https://sndlib.put.poznan.pl/OrlowskiPioroTomaszewskiWessaely2010.bib), [GÉANT topology catalog](https://sndlib.put.poznan.pl/networks.overview.action).

**Uhlig, Quoitin, Lepropre, and Balon**, “Providing Public Intradomain Traffic Matrices to the Research Community,” *ACM SIGCOMM Computer Communication Review* 36(1), 83–86, 2006, DOI [10.1145/1111322.1111341](https://doi.org/10.1145/1111322.1111341). [Author-hosted paper](https://inlold.info.ucl.ac.be/system/files/traffic-matrices.pdf). It explains that GÉANT matrices were assembled from IGP routing, sampled NetFlow, and BGP information at 15-minute intervals. The authors state that time information in the public matrices was anonymized.

- **What we used:** The published GÉANT connectivity and measured-derived dynamic demand matrices. SNDlib lists the full GÉANT instance as 22 nodes/36 links and 11,460 matrices at 15-minute granularity; our scenario retains eight nodes, eleven physical links, six directed OD series, and 42 calendar days. [SNDlib topology catalog](https://sndlib.put.poznan.pl/networks.overview.action), [dynamic catalog](https://sndlib.put.poznan.pl/dynamicmatrices.overview.action), [project data provenance](DATA_SOURCES.md).
- **What we did not use:** The full network, all OD demands, SNDlib's default peak `DEMANDS` section as a training series, or production GÉANT link capacities/delays. Our 10 Mbps directed capacity and propagation formula are **scenario assumptions**. Uhlig et al. say the public matrix time information was anonymized, so the apparent 2005 dates should **not** be treated as verified original calendar dates. Matching the traffic sequence to 2022–2024 carbon days by month/weekday is a **constructed counterfactual mapping**, not historical synchronization or an empirically validated seasonal match. [Uhlig et al.](https://inlold.info.ucl.ac.be/system/files/traffic-matrices.pdf), [SNDlib dynamic catalog](https://sndlib.put.poznan.pl/dynamicmatrices.overview.action), [method](METHODOLOGY.md).
- **Citation detail:** SNDlib explicitly asks users of *dynamic matrices* to cite its references **[3] and [4]**, which are **Idzikowski et al., “Dynamic routing at different layers in IP-over-WDM networks—Maximizing energy savings” (2011)** and **Koster, Kutschka, and Raack, “Towards Robust Network Design using Integer Linear Programming Techniques” (NGI 2010)**. These are catalog-requested dataset citations, **not algorithms implemented here**. Include them alongside SNDlib and Uhlig in a formal paper. [SNDlib request](https://sndlib.put.poznan.pl/dynamicmatrices.overview.action), [reference 3 BibTeX](https://sndlib.put.poznan.pl/IdzikowskiOrlowskiRaackWoesnerWolisz2010b.bib), [reference 4 BibTeX](https://sndlib.put.poznan.pl/KosterKutschkaRaack2010.bib).

### 9. ECON-PowerCI — country-level carbon input

**Zhang, Zhao, Zhu, et al.**, “A near-real time daily European Power Consumption and Carbon Intensity Dataset (ECON-PowerCI),” *Scientific Data* 12, article 1693, 2025, DOI [10.1038/s41597-025-05978-7](https://doi.org/10.1038/s41597-025-05978-7). [Dataset v2 on Zenodo](https://doi.org/10.5281/zenodo.15987717).

- **Paper's point:** Provides **daily**, country-level, **consumption-based** electricity CO₂ intensity, accounting for cross-border electricity flows; coverage is 2015–2024 across 35 European countries. Its input processing uses finer-grained electricity records but the published `Value` we use is daily kg CO₂/MWh. It documents quality flags and country coverage gaps. [Scientific Data, methods and data records](https://doi.org/10.1038/s41597-025-05978-7).
- **What we used:** The dataset's daily `Value` for eight node countries, retaining quality flags; 2022–2024 country days were mapped by month/weekday to the traffic sequence to create **counterfactual** scenarios. Since the source traffic calendar was anonymized, this is a reproducible scenario rule, not a claim that the two datasets' seasons or weekdays truly correspond. One carbon value is held across a day's 96 traffic intervals. [Dataset](https://doi.org/10.5281/zenodo.15987717), [Uhlig et al.](https://inlold.info.ucl.ac.be/system/files/traffic-matrices.pdf), [project method](METHODOLOGY.md).
- **What we did not use:** A real-time API, 15-minute or hourly carbon forecasts, marginal or life-cycle emissions, or contemporaneously measured 2005 electricity intensity. The project does not forecast carbon. Its score multiplies a proxy path cost by served bytes but lacks observed energy use, so it cannot be interpreted as actual grams emitted. [Scientific Data, data records](https://doi.org/10.1038/s41597-025-05978-7), [project method](METHODOLOGY.md).

## Future-method references — cited for proposed experiments only

**Wu, Pan, Long, Jiang, and Zhang**, “Graph WaveNet for Deep Spatial-Temporal Graph Modeling,” *IJCAI*, 2019, DOI [10.24963/IJCAI.2019/264](https://doi.org/10.24963/IJCAI.2019/264). [Official paper](https://www.ijcai.org/proceedings/2019/0264.pdf). It learns adaptive graph dependence because a fixed adjacency may miss latent relationships. This motivates a possible **future** learned-adjacency ablation; Graph WaveNet is **not implemented** in CarbonRoute and its road-traffic results do not predict ours.

## Claims to use in the review and paper

- Say: **“We evaluate a forecast-informed carbon-aware routing loop with conservative capacity safeguards and a joint carbon-budget variant on a controlled, historical GÉANT replay.”** [Project method](METHODOLOGY.md), [joint selector](JOINT_SELECTOR.md).
- Say: **“The data are real source datasets, combined in a simulated counterfactual; the carbon metric is a comparative forwarding score.”** [SNDlib](https://sndlib.put.poznan.pl/dynamicmatrices.overview.action), [ECON-PowerCI](https://doi.org/10.1038/s41597-025-05978-7), [project method](METHODOLOGY.md).
- Do **not** say: “first predictive carbon-aware routing,” “we implemented RouteNet/DCRNN/NeuRoute/CIRo,” “live European carbon,” “measured CO₂ savings,” “measured packet latency,” or “GNN beats all forecasting baselines.” [CIRo](https://scionproto-contrib.github.io/publications/pdfs/2023/green_routing2023.pdf), [NeuRoute](https://dl.ifip.org/db/conf/cnsm/cnsm2017/1570395499.pdf), [RouteNet](https://arxiv.org/abs/1910.01508), [project findings](../results/paper/FINDINGS.md).

For paper submission, independently confirm final bibliography formatting, dataset redistribution terms, and the source archive's requested citations. Public access to a dataset or author PDF does not itself grant unrestricted republication rights. [Project provenance note](DATA_SOURCES.md).
