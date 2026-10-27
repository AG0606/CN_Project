"""Build the editable LaTeX article from the audited Markdown manuscript."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

from manuscript_figures import render

ROOT = Path(__file__).resolve().parents[1]
KEYS = ["sndlib2010", "uhlig2006", "econ2025", "econdata2025", "abilenedata", "epaegrid",
        "ciro2023", "cate2023", "smore2018", "dote2023", "dynamic2011", "robust2010",
        "kipf2017", "cho2014"]
PREAMBLE = r"""\documentclass[conference,letterpaper]{IEEEtran}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{amsmath,amssymb,graphicx,booktabs,tabularx,array}
\usepackage{xurl,cite}
\usepackage[hidelinks]{hyperref}
\hypersetup{pdftitle={Evaluating Predictive Carbon-Aware Routing},
 pdfauthor={Ashutosh Gupta, Tanay Mohta, Avaneesh Chavan}}
\setlength{\emergencystretch}{1em}
\renewcommand{\arraystretch}{1.15}
\newcolumntype{Y}{>{\raggedright\arraybackslash}X}
\newcolumntype{Z}{>{\centering\arraybackslash}X}
\title{Evaluating Predictive Carbon-Aware Routing:
Forecasting and Multipath Trade-offs on G\'{E}ANT and Abilene}
\author{\IEEEauthorblockN{Ashutosh Gupta}
\and\IEEEauthorblockN{Tanay Mohta}
\and\IEEEauthorblockN{Avaneesh Chavan}}
\begin{document}
\maketitle
"""


def escaped(value: str) -> str:
    replacements = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$",
                    "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}",
                    "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
                    "₂": r"$_2$", "×": r"$\times$", "±": r"$\pm$", "≤": r"$\leq$",
                    "≥": r"$\geq$", "→": r"$\rightarrow$", "↑": r"$\uparrow$",
                    "↓": r"$\downarrow$", "−": "-", "–": "--", "—": "---",
                    "Δ": r"$\Delta$", "⁻": "-", "⁶": "6", "“": "``", "”": "''",
                    "‘": "`", "’": "'"}
    return "".join(replacements.get(char, char) for char in value)


def inline(value: str, citations: bool = True) -> str:
    tokens: list[str] = []

    def keep(rendered: str) -> str:
        tokens.append(rendered)
        return f"ZZTOKEN{len(tokens)-1}ZZ"

    value = value.replace("10⁻⁶", keep(r"$10^{-6}$"))
    value = re.sub(r"\bTable ([1-4])\b", lambda m: keep("Table~\\ref{tab:"+str(int(m[1])+1)+"}"), value)

    def hyperlink(match: re.Match) -> str:
        label, target = match.group(1), match.group(2)
        if target.startswith("http"):
            return keep(r"\href{"+target.replace("%", r"\%")+"}{"+escaped(label)+"}")
        return keep(escaped(label))

    value = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", hyperlink, value)
    value = re.sub(r"`([^`]+)`", lambda m: keep(r"\texttt{"+escaped(m[1])+"}"), value)
    value = re.sub(r"\*\*(.+?)\*\*", lambda m: keep(r"\textbf{"+escaped(m[1])+"}"), value)
    value = re.sub(r"\*([^*]+)\*", lambda m: keep(r"\emph{"+escaped(m[1])+"}"), value)
    for name, math in {"m_h": "m_h", "w_fp": "w_{fp}", "u*": "u^*"}.items():
        value = re.sub(r"(?<![\w])"+re.escape(name)+r"(?![\w])", lambda m, math=math: keep("$"+math+"$"), value)
    if citations:
        def citation(match: re.Match) -> str:
            numbers = []
            for part in match[1].split(","):
                bounds = re.split("[–-]", part.strip())
                numbers.extend(range(int(bounds[0]), int(bounds[-1])+1))
            if any(n < 1 or n > len(KEYS) for n in numbers):
                return match[0]
            return keep(r"\cite{"+",".join(KEYS[n-1] for n in numbers)+"}")
        value = re.sub(r"\[(\d+(?:\s*[,–-]\s*\d+)*)\]", citation, value)
    value = escaped(value)
    for i, rendered in enumerate(tokens):
        value = value.replace(f"ZZTOKEN{i}ZZ", rendered)
    return value


def table(lines: list[str], caption: str, count: int) -> str:
    rows = [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in lines]
    rows.pop(1)
    cols = len(rows[0])
    single_column = count == 2
    environment = "table" if single_column else "table*"
    width = r"\columnwidth" if single_column else r"\textwidth"
    if single_column:
        spec = r"p{.47in}ZZZ"
    elif count == 1:
        spec = r"p{.65in}YYY"
    elif cols == 6:
        spec = r"p{.48in}p{1.36in}ZZZZ"
    elif cols == 4 and "planner" in rows[0][0]:
        spec = r"p{1.86in}ZZZ"
    elif cols == 6 and "Mbps" in rows[1][0]:
        spec = r"p{.7in}ZZZZZ"
    else:
        spec = "Y"+"Z"*(cols-1)
    if cols == 6 and "Mbps" in rows[1][0]:
        spec = r"p{.65in}ZZZZZ"
    body = []
    for k, row in enumerate(rows):
        cells = []
        for cell in row:
            rendered = inline(cell, citations=False)
            if k == 0:
                rendered = r"\textbf{"+rendered+"}"
            if " → " in cell:
                a, b = cell.split(" → ")
                rendered = r"\shortstack{"+inline(a)+r"\\$\rightarrow$ "+inline(b)+"}"
            elif " / " in cell and re.match(r"^\d", cell):
                a, b = cell.split(" / ")
                rendered = r"\shortstack{"+inline(a)+r"\\"+inline(b)+"}"
            elif single_column and " ± " in cell:
                mean, spread = cell.split(" ± ")
                rendered = r"\shortstack{"+inline(mean)+r"\\$\pm$ "+inline(spread)+"}"
            cells.append(rendered)
        body.append(" & ".join(cells)+r" \\")
        if k == 0:
            body.append(r"\midrule")
    return (f"\n\\begin{{{environment}}}[!t]\n\\centering\n\\caption{{"+inline(caption, False)+"}\n"
            +f"\\label{{tab:{count}}}\n\\footnotesize\n\\setlength{{\\tabcolsep}}{{4pt}}\n"
            +r"\begin{tabularx}{"+width+"}{"+spec+"}\n\\toprule\n"
            +"\n".join(body)+f"\n\\bottomrule\n\\end{{tabularx}}\n\\end{{{environment}}}\n")


def build(root: Path) -> None:
    folder = root / "docs/paper"
    source = root / "docs/PAPER_DRAFT.md"
    evidence = root / "results/final-validation-20261027"
    audit = json.loads((evidence / "AUDIT.json").read_text())
    if hashlib.sha256((evidence / "summary.csv").read_bytes()).hexdigest() != audit["summary_sha256"]:
        raise ValueError("Changed audited evidence")
    (folder / "images").mkdir(parents=True, exist_ok=True)
    render(root, folder)
    shutil.copy2(root / "docs/REFERENCES.bib", folder / "references.bib")
    text = source.read_text(encoding="utf-8-sig")
    before_refs, refs = text.split("## References", 1)
    lines = before_refs.splitlines()
    out, index, table_count, caption = [PREAMBLE], 0, 0, ""
    in_list = False
    while index < len(lines):
        line = lines[index]
        if index < 6 or not line.strip():
            index += 1
            continue
        numbered = re.match(r"^\d+\. (.+)", line)
        if not numbered and in_list:
            out.append(r"\end{enumerate}")
            in_list = False
        if line == "## Abstract":
            index += 1
            while not lines[index].strip():
                index += 1
            out.append("\\begin{abstract}\n"+inline(lines[index])+"\n\\end{abstract}\n")
        elif line.startswith("**Keywords:"):
            keywords = re.sub(r"^\*\*Keywords:\*\*\s*", "", line)
            out.append("\\begin{IEEEkeywords}\n"+inline(keywords)+"\n\\end{IEEEkeywords}\n")
        elif line.startswith("## "):
            heading = re.sub(r"^\d+\.\s*", "", line[3:])
            out.append("\\section{"+escaped(heading)+"}\n")
        elif line.startswith("### "):
            heading = re.sub(r"^\d+\.\d+\s*", "", line[4:])
            out.append("\\subsection{"+escaped(heading)+"}\n")
        elif line.startswith("**Table "):
            caption = re.sub(r"^\*\*Table \d+\.\*\*\s*", "", line)
        elif line.startswith("|"):
            selected = []
            while index < len(lines) and lines[index].startswith("|"):
                selected.append(lines[index])
                index += 1
            table_count += 1
            out.append(table(selected, caption or "Chronological training, validation and final test periods.", table_count))
            caption = ""
            continue
        elif line.startswith("!["):
            target = re.search(r"\(([^)]+)\)", line)[1]
            stem = Path(target).stem
            index += 1
            while not lines[index].strip():
                index += 1
            figure_caption = re.sub(r"^\*\*Figure \d+\.\*\*\s*", "", lines[index])
            environment = "figure" if stem == "seed_forecast_error" else "figure*"
            width = r"\columnwidth" if environment == "figure" else r"\textwidth"
            out.append(f"\\begin{{{environment}}}[!t]\n\\centering\n"
                       +r"\includegraphics[width="+width+"]{images/"+stem+".pdf}\n"
                       +r"\caption{"+inline(figure_caption)+f"}}\n\\end{{{environment}}}\n")
        elif line.startswith("```"):
            block = []
            index += 1
            while not lines[index].startswith("```"):
                block.append(lines[index])
                index += 1
            wrapped = []
            for command in block:
                parts = command.split(" ")
                wrapped.append(" `\n  ".join(parts) if len(command) > 45 else command)
            out.append("{\\footnotesize\n\\begin{verbatim}\n"+"\n".join(wrapped)+"\n\\end{verbatim}\n}\n")
        elif line == r"\[":
            block = [line]
            index += 1
            while lines[index] != r"\]":
                block.append(lines[index])
                index += 1
            out.append("\n".join(block+[r"\]"])+"\n")
        elif line.startswith("Let X_t be"):
            out.append(r"""Let $X_t$ be the normalized demand matrix, $A$ the fixed normalized
adjacency and $M$ the active-OD mask. For each observed step,
\begin{equation}
 Z_t = \operatorname{ReLU}([X_t,AX_t]W_s+b_s).
\end{equation}
A node-shared GRU encodes $Z_{t-12},\ldots,Z_{t-1}$. Its output head produces
a horizon-specific correction $R_h$, giving
\begin{equation}
\begin{split}
 \widehat X_{t+h-1}&=\max(0,X_{t-1}+R_h)\odot M,\\
 &\hspace{1em}h\in\{1,2,3\}.
\end{split}
\end{equation}
Multiplying elementwise by the frozen per-OD scale restores Mbps.
Adjacency is fixed, not a learned traffic-dependency graph.
""")
        elif line.startswith("More formally, let e_f"):
            out.append(r"""Let $e_f=\max_h(\widehat d_{fh}+m_h)$ and
$\bar d_f=\frac13\sum_h(\widehat d_{fh}+m_h)$.
With path incidence $a_{lfp}$ and capacity $C_l$, the first LP is
\begin{align}
 \min_{w,u}\quad &u \\
 \text{subject to}\quad &\sum_{f,p} a_{lfp}e_fw_{fp}\leq uC_l \quad \forall l,\\
 &\sum_p w_{fp}=1,\quad w_{fp}\geq0 \quad \forall f,p.
\end{align}
The carbon stage minimizes $\sum_{f,p}\bar d_fq_pw_{fp}$ under the fixed
peak limit. The final stage minimizes $\sum_{f,p}|w_{fp}-w^{\rm prev}_{fp}|$
while preserving preceding objective values within solver tolerance.
This avoids a scalar carbon/congestion trade-off weight; the fixed 0.8 guard
still defines an explicit planning preference.
""")
        elif line.startswith("Let a_lfp indicate"):
            out.append(r"""For effective link--OD incidence and offered rate,
\begin{equation}
 B_{lf}=\sum_pa_{lfp}w_{fp},\qquad L_l=\sum_fB_{lf}D_f.
\end{equation}
Equal-rate progressive filling allocates $s_f\leq D_f$ subject to
$\sum_fB_{lf}s_f\leq C_l$. Each OD receives one fairness share regardless of
subpath count; splitting cannot create extra shares.
""")
        elif line.startswith("For intensity c_v"):
            out.append(r"""For intensity $c_v$, path attribution is
$q_{pt}=\sum_{v\text{ forwarding on }p}c_{vt}$, excluding the destination.
For bin duration $\Delta$ seconds, served path bytes are
$b_{ftp}=s_{ft}w_{ftp}\Delta/8$ decimal MB. The run score is
""")
        elif numbered:
            if not in_list:
                out.append(r"\begin{enumerate}")
                in_list = True
            out.append(r"\item "+inline(numbered[1])+"\n")
        else:
            out.append(inline(line)+"\n")
        index += 1
    if in_list:
        out.append(r"\end{enumerate}")
    entries = re.findall(r"^\d+\. (.+)$", refs, re.M)
    if len(entries) != len(KEYS):
        raise ValueError("Reference count mismatch")
    out.append("\\bibliographystyle{IEEEtran}\n\\bibliography{references}\n\\end{document}\n")
    result = "\n".join(out)
    (folder / "main.tex").write_text(result, encoding="utf-8")
    files = [source, root / "docs/REFERENCES.bib", folder / "main.tex", folder / "references.bib",
             *sorted((folder / "images").glob("*.pdf"))]
    manifest = {"summary_sha256": audit["summary_sha256"], "audited_runs": audit["runs"],
                "source": "docs/PAPER_DRAFT.md", "format": "IEEEtran conference, letter, two columns",
                "bibliography_style": "IEEEtran", "reference_count": len(entries),
                "table_count": table_count, "figure_count": 3,
                "sha256": {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    (folder / "build_manifest.json").write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    (folder / "COMPILE_CHECK.json").write_text(json.dumps({"status": "pending",
          "format": manifest["format"], "main_sha256": hashlib.sha256(result.encode()).hexdigest()}, indent=2)+"\n", encoding="utf-8")
    print(f"Built {folder / 'main.tex'}: {table_count} tables, 3 figures, {len(entries)} references")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    build(args.root.resolve())
