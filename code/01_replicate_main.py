# -*- coding: utf-8 -*-
"""
01_replicate_main.py — 复现 Card & Krueger (1994, AER) 的表 2、表 3、表 4 与图 1。

输入：data/raw/public.csv（410 家快餐店门店级调查数据，46 列）
输出：results/tables/table2_means.csv、table3_employment.csv、table4_regressions.csv
      results/figures/figure1_wage_distribution.png
运行：python code/01_replicate_main.py
"""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")          # 无界面环境下也能保存图
import matplotlib.pyplot as plt
import statsmodels.api as sm

RAW = Path("data/raw")
OUT_TAB = Path("results/tables")
OUT_FIG = Path("results/figures")
OUT_TAB.mkdir(parents=True, exist_ok=True)
OUT_FIG.mkdir(parents=True, exist_ok=True)


def load_data():
    """读入 public.csv：空白当缺失(NaN)，全部转数值。"""
    df = pd.read_csv(RAW / "public.csv")
    df = df.replace(r"^\s*$", np.nan, regex=True)
    for c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def construct(df):
    """构造派生变量。"""
    # 全职当量就业 FTE = 全职 + 经理 + 0.5*兼职（兼职按半个全职计）
    df["fte1"] = df["EMPFT"] + df["NMGRS"] + 0.5 * df["EMPPT"]
    df["fte2"] = df["EMPFT2"] + df["NMGRS2"] + 0.5 * df["EMPPT2"]
    df["demp"] = df["fte2"] - df["fte1"]       # 就业变化

    # 初始工资缺口 gap：PA 或 NJ 初始工资>=5.05 时为 0；否则 = (5.05-wage)/wage
    df["gap"] = np.nan
    df.loc[df["STATE"] == 0, "gap"] = 0.0
    nj = df["STATE"] == 1
    df.loc[nj & (df["WAGE_ST"] >= 5.05), "gap"] = 0.0
    df.loc[nj & (df["WAGE_ST"] > 0) & (df["WAGE_ST"] < 5.05), "gap"] = (5.05 - df["WAGE_ST"]) / df["WAGE_ST"]

    # 全职占比（按 FTE 口径）、套餐价格
    df["fracft"] = df["EMPFT"] / df["fte1"]
    df["fracft2"] = df["EMPFT2"] / df["fte2"]
    df["pmeal"] = df["PSODA"] + df["PFRY"] + df["PENTREE"]
    df["pmeal2"] = df["PSODA2"] + df["PFRY2"] + df["PENTREE2"]

    # 州 × 初始工资档分组（用于表 3）
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


def mean_se_t(df, varname):
    """返回 (NJ均值, NJ标准误, PA均值, PA标准误, t统计量)。"""
    v_nj = df.loc[df.STATE == 1, varname].dropna()
    v_pa = df.loc[df.STATE == 0, varname].dropna()
    se_nj = v_nj.std(ddof=1) / np.sqrt(len(v_nj))
    se_pa = v_pa.std(ddof=1) / np.sqrt(len(v_pa))
    t = (v_nj.mean() - v_pa.mean()) / np.sqrt(se_nj**2 + se_pa**2)
    return v_nj.mean(), se_nj, v_pa.mean(), se_pa, t


def pct_row(df, varname):
    """百分比变量：均值/标准误×100，t 保持不变。"""
    m_nj, se_nj, m_pa, se_pa, t = mean_se_t(df, varname)
    return 100*m_nj, 100*se_nj, 100*m_pa, 100*se_pa, t


def table2(df):
    """表 2：各变量均值（按州，第一波/第二波）。"""
    df["at425"] = (df["WAGE_ST"] == 4.25).astype(float)
    df["at425_2"] = (df["WAGE_ST2"] == 4.25).astype(float)
    df["at505_2"] = (df["WAGE_ST2"] == 5.05).astype(float)
    rows = {
        "第1波 FTE就业": mean_se_t(df, "fte1"),
        "第1波 全职占比(%)": pct_row(df, "fracft"),
        "第1波 起始工资": mean_se_t(df, "WAGE_ST"),
        "第1波 工资=$4.25(%)": pct_row(df, "at425"),
        "第1波 套餐价格": mean_se_t(df, "pmeal"),
        "第1波 营业小时": mean_se_t(df, "HRSOPEN"),
        "第1波 招募奖金(%)": pct_row(df, "BONUS"),
        "第2波 FTE就业": mean_se_t(df, "fte2"),
        "第2波 全职占比(%)": pct_row(df, "fracft2"),
        "第2波 起始工资": mean_se_t(df, "WAGE_ST2"),
        "第2波 工资=$4.25(%)": pct_row(df, "at425_2"),
        "第2波 工资=$5.05(%)": pct_row(df, "at505_2"),
        "第2波 套餐价格": mean_se_t(df, "pmeal2"),
        "第2波 营业小时": mean_se_t(df, "HRSOPEN2"),
        "第2波 招募奖金(%)": pct_row(df, "SPECIAL2"),
    }
    tab = pd.DataFrame(rows, index=["NJ均值", "NJ标准误", "PA均值", "PA标准误", "t"]).T
    tab.columns = ["NJ均值", "NJ标准误", "PA均值", "PA标准误", "t统计量"]
    return tab.round(2)


def rstat(g):
    """对某组返回 行1~行5 的 (mean, se)。"""
    m1, se1 = g["fte1"].mean(), g["fte1"].std(ddof=1) / np.sqrt(g["fte1"].count())
    m2, se2 = g["fte2"].mean(), g["fte2"].std(ddof=1) / np.sqrt(g["fte2"].count())
    bal = g.loc[g.fte1.notna() & g.fte2.notna()]
    d4 = bal["fte2"] - bal["fte1"]
    m4, se4 = d4.mean(), d4.std(ddof=1) / np.sqrt(len(d4))
    chg3 = m2 - m1
    se3 = se4
    base5 = g.loc[g.fte1.notna() & (g.fte2.notna() | g.STATUS2.isin([2, 4, 5]))].copy()
    base5["fte2_5"] = base5["fte2"].where(base5["fte2"].notna(), 0.0)
    d5 = base5["fte2_5"] - base5["fte1"]
    m5, se5 = d5.mean(), d5.std(ddof=1) / np.sqrt(len(d5))
    return [(m1, se1), (m2, se2), (chg3, se3), (m4, se4), (m5, se5)]


def table3(df):
    """表 3：每家门店平均 FTE 就业（前后 + DiD）。"""
    groups = {"PA": (df.STATE == 0), "NJ": (df.STATE == 1),
              "NJ_low": (df.group == "NJ_low"), "NJ_mid": (df.group == "NJ_mid"),
              "NJ_high": (df.group == "NJ_high")}
    res = {k: rstat(df[v]) for k, v in groups.items()}

    def fmt(p):
        return f"{p[0]:.2f} ({p[1]:.2f})"

    def diff(a, b):
        return (a[0]-b[0], np.sqrt(a[1]**2 + b[1]**2))

    rows = ["1 第一波FTE(全部可用)", "2 第二波FTE(全部可用)", "3 平均FTE变化(非平衡)",
            "4 平均FTE变化(平衡)", "5 平均FTE变化(临时关闭=0)"]
    tab = pd.DataFrame(index=rows)
    tab["PA"] = [fmt(res["PA"][i]) for i in range(5)]
    tab["NJ"] = [fmt(res["NJ"][i]) for i in range(5)]
    tab["NJ-PA"] = [fmt(diff(res["NJ"][i], res["PA"][i])) for i in range(5)]
    tab["NJ低薪$4.25"] = [fmt(res["NJ_low"][i]) for i in range(5)]
    tab["NJ中档"] = [fmt(res["NJ_mid"][i]) for i in range(5)]
    tab["NJ高薪≥$5.00"] = [fmt(res["NJ_high"][i]) for i in range(5)]
    tab["低薪-高薪"] = [fmt(diff(res["NJ_low"][i], res["NJ_high"][i])) for i in range(5)]
    tab["中档-高薪"] = [fmt(diff(res["NJ_mid"][i], res["NJ_high"][i])) for i in range(5)]
    return tab.T


def table4(df):
    """表 4：就业变化的简化式回归（5 个设定）。"""
    df["dwage"] = df["WAGE_ST2"] - df["WAGE_ST"]
    sub = df[df["demp"].notna() & ((df["STATUS2"] == 3) | df["dwage"].notna())].copy()
    sub["bk"] = (sub["CHAIN"] == 1).astype(float)
    sub["kfc"] = (sub["CHAIN"] == 2).astype(float)
    sub["roys"] = (sub["CHAIN"] == 3).astype(float)

    specs = [
        ("(i) NJ", ["STATE"], "STATE"),
        ("(ii) NJ+连锁/直营", ["STATE", "bk", "kfc", "roys", "CO_OWNED"], "STATE"),
        ("(iii) GAP", ["gap"], "gap"),
        ("(iv) GAP+连锁/直营", ["gap", "bk", "kfc", "roys", "CO_OWNED"], "gap"),
        ("(v) GAP+连锁+地区", ["gap", "bk", "kfc", "roys", "CENTRALJ", "SOUTHJ", "PA1", "PA2"], "gap"),
    ]
    rows = []
    for name, xv, key in specs:
        X = sm.add_constant(sub[xv])
        fit = sm.OLS(sub["demp"], X).fit()
        rows.append({"模型": name, "系数": fit.params[key], "标准误": fit.bse[key],
                     "√MSE": np.sqrt(fit.mse_resid), "样本量": int(fit.nobs),
                     "R²": fit.rsquared})
    return pd.DataFrame(rows).set_index("模型").round(4)


def figure1(df):
    """图 1：起始工资分布（2×2：NJ/PA × 第一波/第二波）。"""
    fig, axes = plt.subplots(2, 2, figsize=(10, 7), sharex=True)
    bins = np.arange(4.0, 6.5, 0.25)
    for col, st in [(0, 1), (1, 0)]:
        lab = "New Jersey" if st == 1 else "Pennsylvania"
        for row, (var, wave) in enumerate([("WAGE_ST", "February 1992"),
                                           ("WAGE_ST2", "November 1992")]):
            ax = axes[row, col]
            s = df.loc[df.STATE == st, var].dropna()
            ax.hist(s, bins=bins, color=("tab:blue" if st == 1 else "tab:orange"),
                    alpha=0.75, edgecolor="white")
            ax.axvline(4.25, color="gray", linewidth=0.8, linestyle="--")
            ax.axvline(5.05, color="gray", linewidth=0.8, linestyle="--")
            if row == 0:
                ax.set_title(lab, fontsize=12)
            if col == 0:
                ax.set_ylabel(wave + "\nNumber of stores", fontsize=10)
    axes[1, 0].set_xlabel("Starting wage ($/hour)")
    axes[1, 1].set_xlabel("Starting wage ($/hour)")
    fig.suptitle("Figure 1  Distribution of starting wage rates", fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(OUT_FIG / "figure1_wage_distribution.png", dpi=150)
    plt.close(fig)


def main():
    df = load_data()
    df = construct(df)

    # 保存处理后的门店级数据（供审阅/复现用）
    PROC = Path("data/processed")
    PROC.mkdir(parents=True, exist_ok=True)
    df.to_csv(PROC / "ck_stores_processed.csv", index=False)
    print("处理后数据已保存 →", PROC / "ck_stores_processed.csv")

    t2 = table2(df)
    t2.to_csv(OUT_TAB / "table2_means.csv")
    print("表 2 已保存 →", OUT_TAB / "table2_means.csv")

    t3 = table3(df)
    t3.to_csv(OUT_TAB / "table3_employment.csv")
    print("表 3 已保存 →", OUT_TAB / "table3_employment.csv")

    t4 = table4(df)
    t4.to_csv(OUT_TAB / "table4_regressions.csv")
    print("表 4 已保存 →", OUT_TAB / "table4_regressions.csv")

    figure1(df)
    print("图 1 已保存 →", OUT_FIG / "figure1_wage_distribution.png")

    # 打印关键结果（与论文对照）
    nj_chg = df.loc[(df.STATE == 1) & df.fte1.notna() & df.fte2.notna()]["demp"].mean()
    pa_chg = df.loc[(df.STATE == 0) & df.fte1.notna() & df.fte2.notna()]["demp"].mean()
    print(f"\n关键核对：NJ 平衡就业变化={nj_chg:.2f}，PA={pa_chg:.2f}，DiD={nj_chg-pa_chg:.2f}")


if __name__ == "__main__":
    main()
