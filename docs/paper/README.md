# CarbonRoute research manuscript

Open this folder in Codex to edit `main.tex` with its automatic PDF preview. The paper uses **IEEE two-column conference format** through `\documentclass[conference,letterpaper]{IEEEtran}`. IEEEtran supplies the default 10 pt typography, margins, columns, section numbering and caption styles; the manuscript does not override the class's page geometry. It includes five tables, three figures, formal equations and fourteen references. Author affiliations and any additional requirements from the chosen conference remain for team review; no affiliation, conference acceptance or submission status is invented.

## Files

- `main.tex` is the complete editable IEEE conference article, with IEEE author blocks and the `IEEEkeywords` environment.
- `references.bib` holds the verified bibliographic records. `\bibliographystyle{IEEEtran}` formats the references and numbers them by first citation. The built-in compiler runs the necessary bibliography processing; a conventional setup should use `latexmk` or the usual LaTeX → BibTeX → LaTeX → LaTeX sequence.
- `images/` holds three standalone vector PDF figures redrawn from unchanged audited CSVs. The forecast figure stacks both networks to fit one column; the capacity and six-panel trade-off figures span both columns. The forecast table fits one column; the larger tables use standard `table*` floats. Original study figures remain untouched.
- `build_manifest.json` records source/figure hashes and the audited summary hash used to build the article.
- `../PAPER_DRAFT.md` is the readable source manuscript. It includes team-facing status information omitted from the typeset article.

## Editing and rebuilding

For reproducible changes, edit `docs/PAPER_DRAFT.md` and run:

```powershell
.\.venv\Scripts\python.exe scripts/build_manuscript.py
```

This recreates `main.tex`, `references.bib`, the three figures and the build manifest. **It overwrites direct edits to the generated LaTeX**, so preserve intentional direct changes or apply them to the builder before regenerating. Plotting uses the project's existing Matplotlib dependency; all other builder code uses Python's standard library. Open the project folder and compile again after rebuilding. Conventional LaTeX installations can also compile `main.tex`; all supporting files are inside this folder.

The data-split table is Table I and the four result tables are Tables II–V. In-text references use LaTeX labels. Figures remain Figs. 1–3. Scientific outcomes are not regenerated or modified by manuscript building. Wide floats follow IEEE's top-of-page placement, so they can appear on a later page than their first text reference.

The standard is based on the [IEEE conference template guidance](https://www.ieee.org/conferences/publishing/templates.html) and the maintained [IEEEtran class](https://ctan.org/pkg/ieeetran). No conference page limit was supplied, so formatting does not discard unfavorable results to meet an assumed limit.

## Evidence and claim limits

The main study is `results/final-validation-20261027/`: 2,058 audited runs, twelve new checkpoints and seven later days per network. Prior joint-budget, training, service-first and multipath campaigns remain supplementary, not pooled fresh-test observations. Report all declared capacities: the favorable 40 Mbps GÉANT comparison does not erase the unfavorable 10 Mbps congested case. Perfect-demand controls are future-aware diagnostics; the carbon score is forwarding attribution, not measured emissions.
