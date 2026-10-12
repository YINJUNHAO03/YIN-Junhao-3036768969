# -*- coding: utf-8 -*-
"""
01_replicate_main.py — replicates Tables 2, 3, 4 and Figure 1 of Card & Krueger
(1994, AER) "Minimum Wages and Employment: A Case Study of the Fast-Food
Industry in New Jersey and Pennsylvania".

The table layout and contents follow the notebook exactly:
  - Table 2 = a store-type distribution table + two wave tables (wave 1 / wave 2),
    cells formatted as "mean (SE)".
  - Table 3 = 5 rows (statistics) x 8 columns (groups), where the row-3
    (unbalanced) standard error uses the two-correlated-means formula
    SE3 = sqrt(SE1^2 + SE2^2 - 2*r*SE1*SE2), r = 0.45.
  - Table 4 = the paper's 6 x 6 layout (Independent variable + columns (i)-(v)).

Input : data/raw/public.csv (410 store-level fast-food survey observations, 46 columns)
Output: results/tables/table2_chain.csv, table2_wave1.csv, table2_wave2.csv,
        table3_employment.csv, table4_regressions.csv
        results/figures/figure1_wage_distribution.png
Run   : python code/01_replicate_main.py
"""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")          # save figures without a display
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import statsmodels.api as sm
from scipy import stats

RAW = Path("data/raw")
OUT_TAB = Path("results/tables")
OUT_FIG = Path("results/figures")
OUT_TAB.mkdir(parents=True, exist_ok=True)
OUT_FIG.mkdir(parents=True, exist_ok=True)


def load_data():
    """Read public.csv: blanks become NaN, then coerce every column to numeric."""
    df = pd.read_csv(RAW / "public.csv")
    df = df.replace(r"^\s*$", np.nan, regex=True)
    for c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def construct(df):
    """Build derived variables."""
    # Full-time-equivalent employment FTE = full-time + managers + 0.5*part-time
    df["fte1"] = df["EMPFT"] + df["NMGRS"] + 0.5 * df["EMPPT"]
    df["fte2"] = df["EMPFT2"] + df["NMGRS2"] + 0.5 * df["EMPPT2"]
    df["demp"] = df["fte2"] - df["fte1"]       # change in employment

    # Initial wage gap: 0 for PA or NJ stores already paying >= 5.05;
    # otherwise (5.05 - wage) / wage
    df["gap"] = np.nan
    df.loc[df["STATE"] == 0, "gap"] = 0.0
    nj = df["STATE"] == 1
    df.loc[nj & (df["WAGE_ST"] >= 5.05), "gap"] = 0.0
    df.loc[nj & (df["WAGE_ST"] > 0) & (df["WAGE_ST"] < 5.05), "gap"] = (5.05 - df["WAGE_ST"]) / df["WAGE_ST"]

    # Fraction full-time (FTE basis), price of a full meal
    df["fracft"] = df["EMPFT"] / df["fte1"]
    df["fracft2"] = df["EMPFT2"] / df["fte2"]
    df["pmeal"] = df["PSODA"] + df["PFRY"] + df["PENTREE"]
    df["pmeal2"] = df["PSODA2"] + df["PFRY2"] + df["PENTREE2"]

    # State x initial-wage-bin groups (used in Table 3)
    def wg(r):
        if r["STATE"] == 0:
            return "PA"
        if r["WAGE_ST"] == 4.25:
            return "NJ_low"
        if 4.25 < r["WAGE_ST"] < 5.00:
            return "NJ_mid"
        if r["WAGE_ST"] >= 5.00:
            return "NJ_high"
        return "NJ_missing"
    df["group"] = df.apply(wg, axis=1)
    return df


def pct_ttest(df, mask):
    """0/1 indicator: NJ-vs-PA share (percentage) equality t-test.

    Returns (NJ %, PA %, t-statistic)."""
    v_nj, v_pa = mask[df.STATE == 1], mask[df.STATE == 0]
    p_nj, p_pa = v_nj.mean(), v_pa.mean()
    se_nj = v_nj.std(ddof=1) / np.sqrt(len(v_nj))
    se_pa = v_pa.std(ddof=1) / np.sqrt(len(v_pa))
    t = (p_nj - p_pa) / np.sqrt(se_nj**2 + se_pa**2)
    return 100 * p_nj, 100 * p_pa, t


def mean_se_t(df, varname, pct=False):
    """Return ("NJ mean (SE)", "PA mean (SE)", t) for one variable.

    Percentage variables (pct=True) are scaled by 100 (percentage points).
    When one group has zero variance (no sampling error — e.g. NJ wave-2
    "wage = $4.25" is exactly 0%), the two-sample t-test degenerates and t is
    reported as '—' (as in the notebook / paper).
    """
    v_nj = df.loc[df.STATE == 1, varname].dropna()
    v_pa = df.loc[df.STATE == 0, varname].dropna()
    se_nj = v_nj.std(ddof=1) / np.sqrt(len(v_nj))
    se_pa = v_pa.std(ddof=1) / np.sqrt(len(v_pa))
    k = 100 if pct else 1
    if se_nj == 0 or se_pa == 0:
        t = "—"
    else:
        t = round((v_nj.mean() - v_pa.mean()) / np.sqrt(se_nj**2 + se_pa**2), 2)
    return f"{k*v_nj.mean():.2f} ({k*se_nj:.2f})", f"{k*v_pa.mean():.2f} ({k*se_pa:.2f})", t


def table2(df):
    """Table 2: store-type distribution + variable means by state (waves 1 & 2).

    Returns (chain_table, wave1_table, wave2_table); cells are "mean (SE)".
    """
    df["at425"] = (df["WAGE_ST"] == 4.25).astype(float)
    df["at425_2"] = (df["WAGE_ST2"] == 4.25).astype(float)
    # Temporarily-closed stores (STATUS2 in {2,4,5}) are excluded from the wave-2
    # wage distribution to match the paper's 85.2% (otherwise the public data add
    # one extra store and give 85.5%).
    df["at505_2"] = ((df["WAGE_ST2"] == 5.05) & ~df["STATUS2"].isin([2, 4, 5])).astype(float)

    # 2a. Store-type distribution (percentage of stores in each state)
    vars_ = {
        "Burger King": (df["CHAIN"] == 1),
        "KFC":         (df["CHAIN"] == 2),
        "Roy Rogers":  (df["CHAIN"] == 3),
        "Wendy's":     (df["CHAIN"] == 4),
        "Company owned": (df["CO_OWNED"] == 1),
    }
    chain = pd.DataFrame([(name, *pct_ttest(df, mask)) for name, mask in vars_.items()],
                         columns=["Variable", "NJ", "PA", "t-statistic"])

    wave1 = {
        "FTE employment":                 ("fte1",     False),
        "Percentage full-time employees": ("fracft",   True),
        "Starting wage":                  ("WAGE_ST",  False),
        "Wage = $4.25 (%)":               ("at425",    True),
        "Price of full meal":             ("pmeal",    False),
        "Hours open (weekday)":           ("HRSOPEN",  False),
        "Recruiting bonus (%)":           ("BONUS",    True),
    }
    wave2 = {
        "FTE employment":                 ("fte2",     False),
        "Percentage full-time employees": ("fracft2",  True),
        "Starting wage":                  ("WAGE_ST2", False),
        "Wage = $4.25 (%)":               ("at425_2",  True),
        "Wage = $5.05 (%)":               ("at505_2",  True),
        "Price of full meal":             ("pmeal2",   False),
        "Hours open (weekday)":           ("HRSOPEN2", False),
        "Recruiting bonus (%)":           ("SPECIAL2", True),
    }

    def make_table(vars_dict):
        return pd.DataFrame(
            [(name, *mean_se_t(df, var, pct)) for name, (var, pct) in vars_dict.items()],
            columns=["Variable", "NJ", "PA", "t-statistic"],
        )

    return chain, make_table(wave1), make_table(wave2)


def rstat(g):
    """Return rows 1-5 (mean, SE) for one group.

    Row 3 (unbalanced change) SE uses the two-correlated-means formula
    SE3 = sqrt(SE1^2 + SE2^2 - 2*r*SE1*SE2), r = 0.45 — NOT the balanced-sample
    paired SE (which would give NJ 0.48 instead of the paper's 0.54).
    """
    m1, se1 = g["fte1"].mean(), g["fte1"].std(ddof=1) / np.sqrt(g["fte1"].count())
    m2, se2 = g["fte2"].mean(), g["fte2"].std(ddof=1) / np.sqrt(g["fte2"].count())
    bal = g.loc[g.fte1.notna() & g.fte2.notna()]
    d4 = bal["fte2"] - bal["fte1"]
    m4, se4 = d4.mean(), d4.std(ddof=1) / np.sqrt(len(d4))
    chg3 = m2 - m1
    se3 = np.sqrt(se1**2 + se2**2 - 2 * 0.45 * se1 * se2)
    base5 = g.loc[g.fte1.notna() & (g.fte2.notna() | g.STATUS2.isin([2, 4, 5]))].copy()
    base5["fte2_5"] = base5["fte2"].where(base5["fte2"].notna(), 0.0)
    d5 = base5["fte2_5"] - base5["fte1"]
    m5, se5 = d5.mean(), d5.std(ddof=1) / np.sqrt(len(d5))
    return [(m1, se1), (m2, se2), (chg3, se3), (m4, se4), (m5, se5)]


def table3(df):
    """Table 3: average FTE employment per store — 5 rows x 8 columns.

    Columns: PA, NJ, NJ-PA, NJ low wage, NJ mid-range, NJ high wage,
    Low-High, Mid-High. Cells are "mean (SE)".
    """
    groups = {"PA": (df.STATE == 0), "NJ": (df.STATE == 1),
              "NJ_low": (df.group == "NJ_low"), "NJ_mid": (df.group == "NJ_mid"),
              "NJ_high": (df.group == "NJ_high")}
    res = {k: rstat(df[v]) for k, v in groups.items()}

    def fmt(p):
        return f"{p[0]:.2f} ({p[1]:.2f})"

    def diff(a, b):
        return (a[0] - b[0], np.sqrt(a[1]**2 + b[1]**2))

    rows = ["1. FTE employment, wave 1 (all available)",
            "2. FTE employment, wave 2 (all available)",
            "3. Change in mean FTE (unbalanced)",
            "4. Change in mean FTE (balanced)",
            "5. Change in mean FTE (temporarily closed = 0)"]
    tab = pd.DataFrame(index=rows)
    for col, key in [("PA", "PA"), ("NJ", "NJ"), ("NJ - PA", None),
                     ("NJ low wage $4.25", "NJ_low"), ("NJ mid-range $4.26-4.99", "NJ_mid"),
                     ("NJ high wage >= $5.00", "NJ_high"),
                     ("Low - High", None), ("Mid - High", None)]:
        if key is not None:
            vals = res[key]
        elif col == "NJ - PA":
            vals = [diff(res["NJ"][i], res["PA"][i]) for i in range(5)]
        elif col == "Low - High":
            vals = [diff(res["NJ_low"][i], res["NJ_high"][i]) for i in range(5)]
        else:  # Mid - High
            vals = [diff(res["NJ_mid"][i], res["NJ_high"][i]) for i in range(5)]
        tab[col] = [fmt(v) for v in vals]
    return tab


def table4(df):
    """Table 4: reduced-form regressions — the paper's 6 x 6 layout.

    Rows: New Jersey dummy, Initial wage gap, Controls for chain and ownership,
    Controls for region, Standard error of regression, Probability value for controls.
    Columns: Independent variable + (i)-(v). Cells are "coef (SE)".
    """
    df["dwage"] = df["WAGE_ST2"] - df["WAGE_ST"]
    sub = df[df["demp"].notna() & ((df["STATUS2"] == 3) | df["dwage"].notna())].copy()
    sub["bk"] = (sub["CHAIN"] == 1).astype(float)
    sub["kfc"] = (sub["CHAIN"] == 2).astype(float)
    sub["roys"] = (sub["CHAIN"] == 3).astype(float)

    # chain controls = bk, kfc, roys; ownership = CO_OWNED; region = CENTRALJ,
    # SOUTHJ, PA1, PA2. Column (v) = gap + chain + region (EXCLUDES CO_OWNED),
    # which reproduces the paper's 11.91 (7.39).
    specs = [
        ("(i)",   "STATE", []),
        ("(ii)",  "STATE", ["bk", "kfc", "roys", "CO_OWNED"]),
        ("(iii)", "gap",   []),
        ("(iv)",  "gap",   ["bk", "kfc", "roys", "CO_OWNED"]),
        ("(v)",   "gap",   ["bk", "kfc", "roys", "CENTRALJ", "SOUTHJ", "PA1", "PA2"]),
    ]
    labels = [s[0] for s in specs]

    nj_cell, gap_cell, mse_cell, chain_cell, region_cell, p_cell = {}, {}, {}, {}, {}, {}
    for label, key, ctrl in specs:
        X = sm.add_constant(sub[[key] + ctrl])
        fit = sm.OLS(sub["demp"], X).fit()
        cell = f"{fit.params[key]:.2f} ({fit.bse[key]:.2f})"
        (nj_cell if key == "STATE" else gap_cell)[label] = cell
        mse_cell[label] = f"{np.sqrt(fit.mse_resid):.2f}"
        chain_cell[label] = "yes" if any(c in ("bk", "kfc", "roys", "CO_OWNED") for c in ctrl) else "no"
        region_cell[label] = "yes" if any(c in ("CENTRALJ", "SOUTHJ", "PA1", "PA2") for c in ctrl) else "no"
        if ctrl:
            Xr = sm.add_constant(sub[[key]])
            fitr = sm.OLS(sub["demp"], Xr).fit()
            rss_f, rss_r = np.sum(fit.resid**2), np.sum(fitr.resid**2)
            df1, df2 = len(ctrl), int(fit.df_resid)
            F = ((rss_r - rss_f) / df1) / (rss_f / df2)
            p_cell[label] = f"{1 - stats.f.cdf(F, df1, df2):.2f}"
        else:
            p_cell[label] = "—"

    def row_from(d):
        return [d.get(label, "—") for label in labels]

    tab = pd.DataFrame(
        [["New Jersey dummy"] + row_from(nj_cell),
         ["Initial wage gap"] + row_from(gap_cell),
         ["Controls for chain and ownership"] + row_from(chain_cell),
         ["Controls for region"] + row_from(region_cell),
         ["Standard error of regression"] + row_from(mse_cell),
         ["Probability value for controls"] + row_from(p_cell)],
        columns=["Independent variable"] + labels,
    ).set_index("Independent variable")
    return tab


def figure1(df):
    """Figure 1: distribution of starting wages (two panels: Feb / Nov; NJ and PA
    side-by-side on the same scale; broken x-axis 0 — 4.25—5.55).

    Identical to Section 3 of the notebook: NJ solid black bars, PA white hatched
    bars side-by-side within each bin, y-axis = Percent of stores, x-axis = Wage
    range (broken axis: narrow left axis shows only 0, wide right axis 4.25–5.55
    at 0.1 ticks).
    """
    wage_lo, wage_hi = 4.25, 5.55
    bins = np.arange(425, 556, 10) / 100.0   # 0.1-wide bins: 4.25, 4.35, ..., 5.55
    centers = (bins[:-1] + bins[1:]) / 2.0   # bin centers: 4.30, 4.40, ..., 5.50

    panels = [("WAGE_ST", "February 1992", 35, 5),
              ("WAGE_ST2", "November 1992", 90, 10)]

    fig = plt.figure(figsize=(14, 5))
    gs_outer = gridspec.GridSpec(1, 2, figure=fig, wspace=0.18)

    for gi, (gs, (var, title, ymax, ystep)) in enumerate(zip(gs_outer, panels)):
        gs_in = gridspec.GridSpecFromSubplotSpec(1, 2, subplot_spec=gs,
                                                 width_ratios=[1, 18], wspace=0.02)
        ax0 = fig.add_subplot(gs_in[0])   # shows only "0"
        ax = fig.add_subplot(gs_in[1])    # histogram over 4.25–5.55

        bar_w, dx = 0.038, 0.020
        for st, face, hatch, lab, shift in [(1, "black", None, "New Jersey", -dx),
                                            (0, "white", "///", "Pennsylvania", +dx)]:
            s = df.loc[df.STATE == st, var].dropna().clip(lower=wage_lo, upper=wage_hi)
            cnt, _ = np.histogram(s, bins=bins)
            pct = 100.0 * cnt / len(s)
            ax.bar(centers + shift, pct, width=bar_w, facecolor=face, edgecolor="black",
                   hatch=hatch, linewidth=0.5, label=lab)

        ax.axvline(5.05, color="gray", lw=0.8, ls="--")

        ax.set_xlim(wage_lo, wage_hi)
        ax.set_xticks(bins)
        ax.tick_params(axis="x", labelsize=8)
        ax.set_ylim(0, ymax)
        ax.set_yticks(np.arange(0, ymax + 1, ystep))
        ax.set_xlabel("Wage range", fontsize=11)
        ax.set_ylabel("Percent of stores", fontsize=11)
        ax.set_title(title, fontsize=12)
        if gi == 0:
            ax.legend(loc="upper right", fontsize=9, frameon=False)

        ax0.set_xlim(-0.15, 0.15)
        ax0.set_xticks([0.0])
        ax0.set_ylim(0, ymax)
        ax0.set_yticks([])
        ax0.tick_params(axis="y", left=False, labelleft=False)

        ax0.spines["right"].set_visible(False)
        ax.spines["left"].set_visible(False)
        ax0.spines["top"].set_visible(False)
        ax.spines["top"].set_visible(False)
        d = 0.02
        for a, xf in [(ax0, 1.0), (ax, 0.0)]:
            for y0 in (0.46, 0.54):
                a.plot([xf - d, xf + d], [y0 - d, y0 + d], transform=a.transAxes,
                       color="k", lw=1.2, clip_on=False)

    fig.suptitle("Figure 1  Distribution of starting wage rates", fontsize=13)
    fig.savefig(OUT_FIG / "figure1_wage_distribution.png", dpi=150)
    plt.close(fig)


def main():
    df = load_data()
    df = construct(df)

    PROC = Path("data/processed")
    PROC.mkdir(parents=True, exist_ok=True)
    df.to_csv(PROC / "ck_stores_processed.csv", index=False)
    print("Processed data saved ->", PROC / "ck_stores_processed.csv")

    chain, w1, w2 = table2(df)
    chain.to_csv(OUT_TAB / "table2_chain.csv")
    w1.to_csv(OUT_TAB / "table2_wave1.csv")
    w2.to_csv(OUT_TAB / "table2_wave2.csv")
    print("Table 2 saved ->", OUT_TAB / "table2_chain.csv",
          "|", OUT_TAB / "table2_wave1.csv", "|", OUT_TAB / "table2_wave2.csv")

    t3 = table3(df)
    t3.to_csv(OUT_TAB / "table3_employment.csv")
    print("Table 3 saved ->", OUT_TAB / "table3_employment.csv")

    t4 = table4(df)
    t4.to_csv(OUT_TAB / "table4_regressions.csv")
    print("Table 4 saved ->", OUT_TAB / "table4_regressions.csv")

    figure1(df)
    print("Figure 1 saved ->", OUT_FIG / "figure1_wage_distribution.png")

    nj_chg = df.loc[(df.STATE == 1) & df.fte1.notna() & df.fte2.notna()]["demp"].mean()
    pa_chg = df.loc[(df.STATE == 0) & df.fte1.notna() & df.fte2.notna()]["demp"].mean()
    print(f"\nKey check: NJ balanced employment change = {nj_chg:.2f}, "
          f"PA = {pa_chg:.2f}, DiD = {nj_chg-pa_chg:.2f}")


if __name__ == "__main__":
    main()
