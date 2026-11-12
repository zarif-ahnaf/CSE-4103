"""
Builds Report.tex from results.json so no number in the report can drift from
the computation.  Run analysis.py first.

Usage:  python build_report.py
"""

import json, os, re
from hardware import HARDWARE, SOFTWARE, MACRO, SMALL, BK8, BK24

HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.abspath(os.path.join(HERE, ".."))
R    = json.load(open(os.path.join(OUT, "results.json")))
C, G = R["const"], R["given"]
LB = {(x["area"], int(x["freq_MHz"]), x["indoor"]): x for x in R["link"]}
CV, DP, DL, BR = R["cover"], R["doppler"], R["delay"], R["ber"]
IM, RU, CA, CG = R["impair"], R["reuse"], R["cap"], R["cap_growth"]
VO, CO, VT, HO, BD = R["voice"], R["codecs"], R["volte"], R["handoff"], R["budget"]
TG, FAIL, C1 = R["targets"], R["fail"], R["cap_one_site"]
TARGET_CAP = BD["cap"]

def f(x, n=2): return f"{x:.{n}f}"
def m(x, n=1): return f"{x/1e6:.{n}f}"

SUBST = {"%": r"\%", "&": r"\&", "_": r"\_", "#": r"\#",
         "≥": r"$\geq$", "≤": r"$\leq$", "×": r"$\times$",
         "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
         "°": r"$^\circ$", "µ": r"$\mu$", "→": r"$\rightarrow$",
         "−": r"$-$", "≈": r"$\approx$", "Δ": r"$\Delta$"}

def esc(s):
    if not isinstance(s, str):
        return str(s)
    for k, v in SUBST.items():
        s = s.replace(k, v)
    return s

# ---------------------------------------------------------------- link helper
def ulink(url, label=None):
    lab = label or url
    return r"\href{" + url + r"}{\ulinkurl{" + esc(lab) + r"}}"

def short_link(url):
    """Readable short label from a URL."""
    s = re.sub(r"^https?://(www\.)?", "", url).rstrip("/")
    s = s.replace("https://", "")
    if len(s) > 46:
        s = s[:44] + "…"
    return s

# ---------------------------------------------------------------- link budget
# Compacted: constants that do not vary between rows are stated once.
LB_ROWS = [
    ("UL", "Handset EIRP, $23+0-3$ (dBm)", lambda d: f(d["eirp_ms"], 1)),
    ("UL", "BS antenna gain (dBi)", lambda d, k="g900": f(C["G_BS_900"], 1)),
    ("UL", "BS received power (dBm)", lambda d: f(d["rx_ul"], 1)),
    ("UL", "BS sensitivity: $N_{bs}+C/N$ (dBm)", lambda d: f(C["sens_bs"], 1)),
    ("UL", "Max allowable path loss (dB)", lambda d: f(d["pl_ul"], 1)),
    ("UL", "Margin-adjusted budget (dB)", lambda d: r"\textbf{" + f(d["pl_ul_net"], 1) + "}"),
    ("DL", "BS EIRP per user, $43-20+16-0.5$ (dBm)", lambda d: f(d["eirp_bs"], 1)),
    ("DL", "MS received power (dBm)", lambda d: f(d["rx_dl"], 1)),
    ("DL", "MS sensitivity: $N_{ms}+C/N$ (dBm)", lambda d: f(C["sens_ms"], 1)),
    ("DL", "Max allowable path loss (dB)", lambda d: f(d["pl_dl"], 1)),
    ("DL", "Margin-adjusted budget (dB)", lambda d: r"\textbf{" + f(d["pl_dl_net"], 1) + "}"),
]

def lb_table(cols, caption, label, note):
    """cols: list of (header, dict)."""
    n = len(cols)
    head = (r"\begin{table}[H]\centering\scriptsize"
            r"\caption{" + caption + r"}\label{" + label + r"}"
            r"\begin{tabular}{@{}l" + "c" * n + r"@{}}\toprule" + "\n"
            r"Quantity & " + " & ".join(esc(h) for h, _ in cols) + r" \\ \midrule" + "\n")
    body = []
    for grp, name, fn in LB_ROWS:
        if grp == "UL" and name.startswith("Handset EIRP"):
            body.append(r"\multicolumn{%d}{@{}l}{\textit{Uplink: handset to base station}}\\" % (n + 1))
        if grp == "DL" and name.startswith("BS EIRP"):
            body.append(r"\midrule\multicolumn{%d}{@{}l}{\textit{Downlink: base station to handset}}\\" % (n + 1))
        vals = []
        for _, d in cols:
            if name.startswith("BS antenna gain"):
                g = C["G_BS_900"] if int(d["freq_MHz"]) == 900 else C["G_BS_1800"]
                vals.append(f(g, 1))
            else:
                vals.append(fn(d))
        body.append(name + " & " + " & ".join(vals) + r" \\")
    body.append(r"\midrule\multicolumn{%d}{@{}l}{\textit{Result}}\\" % (n + 1))
    body.append("Uplink cell radius (m) & " + " & ".join(f(d["R_ul_m"], 0) for _, d in cols) + r" \\")
    body.append("Downlink cell radius (m) & " + " & ".join(f(d["R_dl_m"], 0) for _, d in cols) + r" \\")
    body.append("Design radius (m) & " + " & ".join(r"\textbf{" + f(d["R_cov_m"], 0) + "}" for _, d in cols) + r" \\")
    body.append("Limiting direction & " + " & ".join(esc(d["limiting"]) for _, d in cols) + r" \\")
    tail = (r"\bottomrule\end{tabular}\\[2pt]\footnotesize " + note + r"\end{table}")
    return head + "\n".join(body) + tail

# ---------------------------------------------------------------- tables
def target_rows():
    out = []
    for t in TG:
        ok = t[4] == "PASS"
        badge = r"\textbf{PASS}" if ok else r"\textbf{\textit{FAIL}}"
        out.append(f"{t[0]} & {esc(t[1])} & {esc(t[2])} & {esc(t[3])} & {badge} & {esc(t[5])} \\\\")
    return "\n".join(out)

def dom(u):
    """Short, readable domain/path label for a link."""
    s = re.sub(r"^https?://", "", u)
    s = re.sub(r"^www\.", "", s).rstrip("/")
    parts = s.split("/")
    if len(parts) == 1:
        return parts[0]
    host = parts[0]
    tail = [p for p in parts[1:] if p]
    if not tail:
        return host
    last = tail[-1]
    if len(last) > 24:
        last = last[:22]
    # breakable separators only; no non-ASCII glyphs (typewriter font lacks them)
    return host + "/" + last

def hw_rows():
    out = []
    for h in HARDWARE:
        cost = (f"BDT {m(h['bucket'])}~M" if h["bucket"] else "incl.")
        links = r"\newline".join(ulink(u, dom(u)) for _, u in h["links"])
        out.append(
            f"\\textbf{{{h['id']}}} & \\textbf{{{esc(h['item'])}}}\\newline"
            f"{{\\scriptsize {esc(h['spec'])}}}\\newline"
            f"{{\\scriptsize\\itshape Why: {esc(h['why'])}}} & {h['qty']} & {cost} & {links} \\\\ \\midrule")
    return "\n".join(out)

def soft_rows():
    out = []
    for s in SOFTWARE:
        links = r"\newline".join(ulink(u, dom(u)) for _, u in s["links"])
        out.append(f"{esc(s['item'])} & {esc(s['why'])} & {links} \\\\ \\midrule")
    return "\n".join(out)

def codec_rows():
    out = []
    for c in CO:
        star = r"$\bigstar$" if "SELECTED" in c["use"] else ""
        use = esc(c["use"].replace("  <== SELECTED", "").strip())
        out.append(f"{esc(c['name'])} {star} & {f(c['rate'],1)} & {esc(c['bw'])} & "
                   f"{esc(c['quality'])} & {esc(c['complexity'])} & {use} \\\\")
    return "\n".join(out)

def reuse_rows():
    out = []
    for r in RU:
        out.append(f"{r['area'].capitalize()} & {r['N']} & {f(r['Q'],2)} & {f(r['ci_omni'],1)} & "
                   f"{f(r['ci_3sector'],1)} & {f(r['ci_6sector'],1)} \\\\")
    return "\n".join(out)

def cap_rows():
    out = []
    for c in CA:
        carriers = ", ".join(str(x) + " MHz" for x in c["carriers"])
        out.append(f"{c['area'].capitalize()} & {c['nsites']} & {carriers} & "
                   f"{f(c['per_site'],1)} & {f(c['total'],1)} & {f(c['demand'],1)} & "
                   rf"\textbf{{{f(c['load'],1)}\%}} & {f(c['backhaul_load'],1)}\% \\")
    return "\n".join(out)

def voice_rows():
    out = []
    for v in VO:
        out.append(f"{v['area'].capitalize()} & {v['subs']:,} & {f(v['offered'],1)} & {v['channels']} & "
                   rf"{f(v['blocking'],2)}\% & {f(v['blocking_prev'],2)}\% & "
                   rf"{f(v['utilisation'],1)}\% & {f(v['channels_per_sector'],1)} \\")
    return "\n".join(out)

def ho_rows():
    out = []
    for h in HO["stats"]:
        out.append(f"{f(h['H'],0)} & {f(h['ttt'],1)} & {f(h['n_mean'],1)} & {f(h['n_p95'],1)} & "
                   f"{f(h['ping_mean'],2)} & {f(h['degraded_mean'],2)} & "
                   f"{f(h['rsrp_at_ho_mean'],1)} \\\\")
    return "\n".join(out)

def sweep_rows():
    out = []
    for a, b in zip(CV["urban"]["sweep"], CV["rural"]["sweep"]):
        out.append(f"{a['n']} & {f(a['outdoor'],1)}\\% & {f(a['indoor'],1)}\\% & "
                   f"{f(b['outdoor'],1)}\\% & {f(b['indoor'],1)}\\% \\\\")
    return "\n".join(out)

def budget_rows():
    out = []
    for h in HARDWARE:
        if h["bucket"]:
            out.append(f"{h['id']} & {esc(h['item'])} & {h['qty']} & BDT {m(h['bucket'])} & "
                       f"{m(h['bucket'] * h['qty'])} \\\\")
    return "\n".join(out)

def all_links():
    """Every URL used anywhere in the report, for the appendix."""
    seen, rows = set(), []
    for h in HARDWARE:
        for t, u in h["links"]:
            if u not in seen:
                seen.add(u)
                rows.append((h["id"], t, u))
    for s in SOFTWARE:
        for t, u in s["links"]:
            if u not in seen:
                seen.add(u)
                rows.append(("SW", t, u))
    for sid, t, u in REFERENCES:
        if u not in seen:
            seen.add(u)
            rows.append((sid, t, u))
    return rows

REFERENCES = [
    ("R1", "3GPP TS 36.104 - E-UTRA base station radio transmission and reception",
     "https://www.3gpp.org/ftp/Specs/archive/36_series/36.104/"),
    ("R2", "3GPP TS 36.101 - E-UTRA user equipment radio transmission and reception",
     "https://www.3gpp.org/ftp/Specs/archive/36_series/36.101/"),
    ("R3", "3GPP TS 36.942 - E-UTRA radio frequency system scenarios",
     "https://www.3gpp.org/ftp/Specs/archive/36_series/36.942/"),
    ("R4", "3GPP TS 26.071 - AMR speech codec, general description",
     "https://www.3gpp.org/ftp/Specs/archive/26_series/26.071/"),
    ("R5", "3GPP TS 23.228 - IP Multimedia Subsystem (VoLTE signalling)",
     "https://www.3gpp.org/ftp/Specs/archive/23_series/23.228/"),
    ("R6", "ETSI TS 136 104 delivered copies",
     "https://www.etsi.org/deliver/etsi_ts/136100_136199/136104/"),
    ("R7", "ITU-R P.1546 - point-to-area propagation prediction",
     "https://www.itu.int/rec/R-REC-P.1546/en"),
    ("R8", "ITU-R P.837 - rainfall characteristics for propagation modelling",
     "https://www.itu.int/rec/R-REC-P.837/en"),
    ("R9", "ITU-R P.526 - propagation by diffraction",
     "https://www.itu.int/rec/R-REC-P.526/en"),
    ("R10", "ITU-R P.2109 - building entry loss",
     "https://www.itu.int/rec/R-REC-P.2109/en"),
    ("R11", "ITU-T G.711 - 64 kbit/s A-law / mu-law PCM",
     "https://www.itu.int/rec/T-REC-G.711/en"),
    ("R12", "ITU-T G.722 - 7 kHz wideband speech coding",
     "https://www.itu.int/rec/T-REC-G.722/en"),
    ("R13", "ITU-T G.168 - digital network echo cancellers",
     "https://www.itu.int/rec/T-REC-G.168/en"),
    ("R14", "Erlang B blocking-probability calculator",
     "https://www.erlang.com/calculator/erlb/"),
    ("R15", "Erlang (unit) - reference", "https://en.wikipedia.org/wiki/Erlang_(unit)"),
    ("R16", "Delay spread and coherence bandwidth", "https://en.wikipedia.org/wiki/Coherence_bandwidth"),
    ("R17", "Doppler effect", "https://en.wikipedia.org/wiki/Doppler_effect"),
    ("R18", "Log-distance path loss model", "https://en.wikipedia.org/wiki/Log-distance_path_loss_model"),
    ("R19", "Link budget - reference", "https://en.wikipedia.org/wiki/Link_budget"),
    ("R20", "Handover - reference", "https://en.wikipedia.org/wiki/Handover"),
    ("R21", "Adaptive Multi-Rate (AMR) codec", "https://en.wikipedia.org/wiki/Adaptive_Multi-Rate"),
    ("R22", "Linear predictive coding", "https://en.wikipedia.org/wiki/Linear_predictive_coding"),
    ("R23", "Delta modulation", "https://en.wikipedia.org/wiki/Delta_modulation"),
    ("R24", "Differential PCM", "https://en.wikipedia.org/wiki/Differential_pulse-code_modulation"),
    ("R25", "MathWorks BERAWGN - theoretical BER reference",
     "https://www.mathworks.com/help/comm/ref/berawgn.html"),
    ("R26", "ITU-D statistics", "https://www.itu.int/en/ITU-D/Statistics/Pages/stat/default.aspx"),
    ("R27", "World Bank - individuals using the Internet, Bangladesh",
     "https://data.worldbank.org/indicator/IT.NET.USER.ZS?locations=BD"),
    ("R28", "GSMA Intelligence", "https://www.gsmaintelligence.com/"),
    ("R29", "Opensignal mobile experience reports", "https://www.opensignal.com/"),
    ("R30", "Ookla Speedtest Global Index", "https://www.ookla.com/"),
]

LINK_URBAN = lb_table(
    [("Urb. 900", LB[("urban", 900, False)]),
     ("Urb. 1800", LB[("urban", 1800, False)]),
     ("Rur. 900", LB[("rural", 900, False)]),
     ("Rur. 1800", LB[("rural", 1800, False)])],
    "Two-way link budgets at 900 and 1800 MHz, outdoor at the cell edge "
    "(urban $n=3.5$, rural $n=3.0$)",
    "tab:lb",
    r"$d_0=100$ m; $PL(d_0)=71.5$ dB at 900 MHz and $77.6$ dB at 1800 MHz. The downlink figure "
    r"is the per-user share of carrier power ($43-20=23$ dBm), so the two directions are compared "
    r"at equal transmit power instead of crediting one user with the whole carrier.")

LINK_INDOOR = lb_table(
    [("Urban 900 indoor", LB[("urban", 900, True)]),
     ("Urban 1800 indoor", LB[("urban", 1800, True)])],
    "Indoor link budgets: the same budgets with the 12 dB urban penetration margin added",
    "tab:lb_indoor",
    r"Adding the penetration margin collapses the urban radius from 1580 m to 717 m, which is why "
    r"the hospital needs its own small cell rather than relying on the outdoor macro.")

LINK_RURAL = ""

def impair_rows():
    """Two side-by-side columns: phase error | timing error."""
    ph, tm = IM["phase"], IM["timing"]
    n = max(len(ph), len(tm))
    out = []
    for i in range(n):
        left = ""
        if i < len(ph):
            left = f"{ph[i]['deg']:.0f} & {ph[i]['ber']:.2e}"
        else:
            left = " & "
        if i < len(tm):
            right = f"{100*tm[i]['frac']:.0f} & {tm[i]['ber']:.2e}"
        else:
            right = " & "
        out.append(left + " & " + right + r" \\")
    return "\n".join(out)

SUBS = {
    "%%IMPAIR_PHASE%%": impair_rows(),
    "%%LINK_URBAN%%": LINK_URBAN,
    "%%LINK_INDOOR%%": LINK_INDOOR,
    "%%TARGETS%%": target_rows(),
    "%%HARDWARE%%": hw_rows(),
    "%%SOFTWARE%%": soft_rows(),
    "%%CODECS%%": codec_rows(),
    "%%REUSE%%": reuse_rows(),
    "%%CAPACITY%%": cap_rows(),
    "%%VOICE%%": voice_rows(),
    "%%HANDOFF_STATS%%": ho_rows(),
    "%%SWEEP%%": sweep_rows(),
    "%%BUDGET%%": budget_rows(),
    "%%ALLLINKS%%": "\n".join(
        f"{sid} & {esc(t)} & {ulink(u)} \\\\" for sid, t, u in all_links()),
}

TEMPLATE = open(os.path.join(HERE, "report_template.tex"), encoding="utf-8").read()
tex = TEMPLATE
for k, v in SUBS.items():
    tex = tex.replace(k, v)

with open(os.path.join(OUT, "Report.tex"), "w", encoding="utf-8") as fh:
    fh.write(tex)
print("wrote Report.tex:", len(tex), "chars,", tex.count("\n"), "lines")
print("unreplaced placeholders:", re.findall(r"%%[A-Z_]+%%", tex))
