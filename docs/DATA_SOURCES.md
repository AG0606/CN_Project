# Data provenance and usage

Input access is free and requires no account or API key. Runtime uses cached files only. All URLs/checksums are recorded in `inputs/raw/sources.json` and the processed/campaign manifests.

| Source | File / role | Verified checksum (MD5) |
|---|---|---|
| [SNDlib topology](https://sndlib.put.poznan.pl/download/sndlib-networks-native/geant.txt) | Full 22-node / 36-link native instance; only its nodes and links are used | `11b943a4330105aaa368dae1a8e6a335` |
| [SNDlib dynamic archive](https://sndlib.put.poznan.pl/download/directed-geant-uhlig-15min-over-4months-ALL-native.tgz) | 11,460 dynamic 15-minute matrices; 39,570,674 bytes | `6d620995ae7cce558392ac58670ba122` |
| [ECON-PowerCI v2](https://zenodo.org/records/15987717) | `ECON-PowerCI_2015_2024.csv`; 4,693,603 bytes | `7609df58ddd32362276b263c9a4517b8` |

The carbon checksum is published by Zenodo. SNDlib checksums pin the files downloaded during implementation, not an independent publisher signature. SHA-256 values are also stored. A mismatch fails rather than silently accepting changed input.

The topology's default `DEMANDS` section is an aggregate peak matrix and is **never used for time-series training**. Dynamic files supply their own time/unit metadata. Source capacities/cost options are not interpreted as measured installed link capacity. See [SNDlib native format](https://sndlib.put.poznan.pl/html/docu/io-formats/native/network.description.html).

The [dynamic matrices catalog](https://sndlib.put.poznan.pl/dynamicmatrices.overview.action) attributes the GÉANT data to Steve Uhlig and asks publications to cite its references [3] and [4]. Retain that attribution and obtain the full bibliographic entries from the catalog before paper submission. The archive contains source attribution in each matrix. Data may include anonymization and conversion inaccuracies.

For carbon, cite Shujie Zhang, **ECON-PowerCI_2015_2024**, Zenodo v2, DOI [10.5281/zenodo.15987717](https://doi.org/10.5281/zenodo.15987717), and the [ECON-PowerCI methodology paper](https://www.nature.com/articles/s41597-025-05978-7). Values concern CO2, not CO2e, lifecycle emissions or marginal emission factors.

The inspected dataset landing page does not supply a clear license value. This project supplies downloader code, hashes and attribution instead of bundling original third-party files in Git or the portable source ZIP. Public download availability does not automatically confer unrestricted redistribution. Check the source terms before publishing raw or derived data with a paper; the package's illustrative outputs do not establish a dataset license.

Related work relevant to framing (not proof of novelty): [CIRo](https://netsec.ethz.ch/publications/papers/green_routing2023.pdf), [NeuRoute](https://arxiv.org/abs/1709.06002). Their prior predictive routing ideas rule out a generic “first predictive carbon routing” claim.
