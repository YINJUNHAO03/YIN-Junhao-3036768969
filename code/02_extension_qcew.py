# -*- coding: utf-8 -*-
"""
02_extension_qcew.py — independent extension: a county-level DiD using BLS QCEW
official data.

Idea: replace the Card-Krueger (1994) store-level phone survey with county-level
aggregates from the BLS administrative wage records (QCEW/ES-202), and test
whether the April 1992 NJ minimum-wage increase reduced employment in NJ counties'
"eating & drinking places" (SIC 58) relative to PA counties.

Input : data/raw/sic_1992_qtrly_by_area.zip (BLS QCEW, SIC classification 1975-2000)
Output: results/tables/extension_did.csv, extension_robustness.csv
        results/figures/extension_employment_change.png
Run   : python code/02_extension_qcew.py
"""
from pathlib import Path
import zipfile, io, re
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import statsmodels.api as sm

RAW = Path("data/raw")
OUT_TAB = Path("results/tables")
OUT_FIG = Path("results/figures")
OUT_TAB.mkdir(parents=True, exist_ok=True)
OUT_FIG.mkdir(parents=True, exist_ok=True)

ZIP = RAW / "sic_1992_qtrly_by_area.zip"
# Robustness check: the 7 eastern PA counties covered by the Card & Krueger (1994)
# phone survey, used as a more comparable control group.
EAST_PA_FIPS = {"42017", "42029", "42069", "42077", "42079", "42091", "42095"}
KEEP_COLS = ["own_code", "industry_code", "agglvl_code", "year", "qtr",
             "disclosure_code", "qtrly_estabs_count",
             "month1_emplvl", "month2_emplvl", "month3_emplvl",
             "total_qtrly_wages", "avg_wkly_wage"]


def load_county_files():
    """Locate NJ (34xxx) / PA (42xxx) county files inside the zip."""
    with zipfile.ZipFile(ZIP) as z:
        all_names = [n for n in z.namelist() if n.endswith(".csv")]
    county = []
    for n in all_names:
        m = re.search(r"\s(\d{5}) \(", n)
        if not m:
            continue
        fips = m.group(1)
        if fips[:2] in ("34", "42") and fips[2:] not in ("000", "998", "999"):
            county.append((fips, n))
    return county


def build_panel(county_files):
    """Read and filter: eating & drinking places (SIC 58/581/5810) x private
    (own_code = 5), into a county x quarter panel."""
    frames = []
    with zipfile.ZipFile(ZIP) as z:
        for fips, name in county_files:
            raw = pd.read_csv(io.BytesIO(z.read(name)))
            eat = raw[(raw["industry_code"] == "SIC_0G581") &
                      (raw["own_code"] == 5)].copy()
            if eat.empty:
                continue
            eat["fips"] = fips
            eat["state"] = fips[:2]
            frames.append(eat[KEEP_COLS + ["fips", "state"]])
    df = pd.concat(frames, ignore_index=True)
    num = ["qtrly_estabs_count", "month1_emplvl", "month2_emplvl",
           "month3_emplvl", "total_qtrly_wages", "avg_wkly_wage"]
    for c in num:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def build_did(df):
    """Build the county-level DiD: before = Feb+Mar, after = Nov+Dec, dlog = log change."""
    q1 = df[df["qtr"] == 1].set_index("fips")
    q4 = df[df["qtr"] == 4].set_index("fips")
    before = (q1["month2_emplvl"] + q1["month3_emplvl"]) / 2.0   # Feb + Mar
    after = (q4["month2_emplvl"] + q4["month3_emplvl"]) / 2.0    # Nov + Dec
    d = pd.DataFrame({"state": q1["state"], "before": before, "after": after}).dropna()
    d["dlog"] = np.log(d["after"]) - np.log(d["before"])
    d["nj"] = (d["state"] == "34").astype(int)
    return d


def _wide(df, outcome, full_quarter):
    """Turn the county x quarter panel into county-level before/after log changes.

    outcome: "employment" or "establishments".
    full_quarter: True uses the full quarter (months 1+2+3 / 10+11+12),
                  False uses months 2-3 / 11-12.
    """
    q1 = df[df["qtr"] == 1].set_index("fips")
    q4 = df[df["qtr"] == 4].set_index("fips")
    if outcome == "employment":
        if full_quarter:
            before = (q1["month1_emplvl"] + q1["month2_emplvl"] + q1["month3_emplvl"]) / 3.0
            after = (q4["month1_emplvl"] + q4["month2_emplvl"] + q4["month3_emplvl"]) / 3.0
        else:
            before = (q1["month2_emplvl"] + q1["month3_emplvl"]) / 2.0
            after = (q4["month2_emplvl"] + q4["month3_emplvl"]) / 2.0
    else:  # establishments (the count is already a quarterly value)
        before = q1["qtrly_estabs_count"]
        after = q4["qtrly_estabs_count"]
    d = pd.DataFrame({"fips": q1.index, "state": q1["state"],
                      "before": before, "after": after}).dropna()
    d["dlog"] = np.log(d["after"]) - np.log(d["before"])
    d["nj"] = (d["state"] == "34").astype(int)
    return d


def _did(d):
    """Run the county-level DiD regression, return (coef, SE, t, p, n)."""
    X = sm.add_constant(d[["nj"]])
    fit = sm.OLS(d["dlog"], X).fit()
    return fit.params["nj"], fit.bse["nj"], fit.tvalues["nj"], fit.pvalues["nj"], int(fit.nobs)


def robustness(df):
    """Robustness checks: alternative control group / window / outcome."""
    rows = []
    d = _wide(df, "employment", full_quarter=False)
    rows.append(("1. Main: employment Feb-Mar vs Nov-Dec, all PA", *_did(d)))

    d2 = d[d["fips"].str[:2].eq("34") | d["fips"].isin(EAST_PA_FIPS)].copy()
    rows.append(("2. Control = eastern PA (7 counties)", *_did(d2)))

    d3 = _wide(df, "employment", full_quarter=True)
    rows.append(("3. Full-quarter window Q1 vs Q4", *_did(d3)))

    d4 = _wide(df, "establishments", full_quarter=False)
    rows.append(("4. Outcome = establishments", *_did(d4)))

    return pd.DataFrame(rows, columns=["Specification", "DiD coefficient", "SE", "t", "p", "N"])


def main():
    county_files = load_county_files()
    print(f"County files: NJ {sum(1 for f, _ in county_files if f.startswith('34'))}, "
          f"PA {sum(1 for f, _ in county_files if f.startswith('42'))}")

    df = build_panel(county_files)
    d = build_did(df)
    print(f"County-level sample: {len(d)} counties (NJ {int(d.nj.sum())}, "
          f"PA {int((1 - d.nj).sum())})")

    # Save the processed county-level panel
    PROC = Path("data/processed")
    PROC.mkdir(parents=True, exist_ok=True)
    d.to_csv(PROC / "qcew_county_panel.csv")
    print("Processed data saved ->", PROC / "qcew_county_panel.csv")

    # DiD means table
    dlog_nj = d.loc[d.nj == 1, "dlog"].mean()
    dlog_pa = d.loc[d.nj == 0, "dlog"].mean()
    did = dlog_nj - dlog_pa

    X = sm.add_constant(d[["nj"]])
    fit = sm.OLS(d["dlog"], X).fit()

    tab = pd.DataFrame({
        "Employment (Feb-Mar)": [d.loc[d.nj == 0, "before"].mean(), d.loc[d.nj == 1, "before"].mean()],
        "Employment (Nov-Dec)": [d.loc[d.nj == 0, "after"].mean(), d.loc[d.nj == 1, "after"].mean()],
        "Log change": [dlog_pa, dlog_nj],
    }, index=["Pennsylvania", "New Jersey"])
    tab.loc["DiD (NJ-PA)"] = [None, None, did]
    tab.to_csv(OUT_TAB / "extension_did.csv")
    print("\nDiD means table saved ->", OUT_TAB / "extension_did.csv")
    print(tab.round(4))

    print(f"\nDiD regression: dlog ~ NJ")
    print(f"  coef = {fit.params['nj']:+.4f}  SE = {fit.bse['nj']:.4f}  "
          f"t = {fit.tvalues['nj']:.3f}  p = {fit.pvalues['nj']:.3f}  n = {int(fit.nobs)}")

    # Distribution of employment changes (with group-mean reference lines and DiD label)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    bins = np.linspace(d["dlog"].min() - 0.02, d["dlog"].max() + 0.02, 18)
    ax.hist(d.loc[d.nj == 1, "dlog"], bins=bins, alpha=0.55, color="tab:blue",
            label="New Jersey (treated)", edgecolor="white")
    ax.hist(d.loc[d.nj == 0, "dlog"], bins=bins, alpha=0.55, color="tab:orange",
            label="Pennsylvania (control)", edgecolor="white")
    ax.axvline(0, color="gray", linewidth=0.8)
    ax.set(xlabel="Log change in Eating & Drinking Places employment",
           ylabel="Number of counties",
           title="1992 change in Eating & Drinking Places employment: NJ vs PA counties (QCEW)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT_FIG / "extension_employment_change.png", dpi=150)
    plt.close(fig)
    print("Extension figure saved ->", OUT_FIG / "extension_employment_change.png")

    # Robustness checks
    rob = robustness(df)
    rob.to_csv(OUT_TAB / "extension_robustness.csv")
    print("\nRobustness checks saved ->", OUT_TAB / "extension_robustness.csv")
    print(rob.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
