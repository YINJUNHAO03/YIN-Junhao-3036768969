# -*- coding: utf-8 -*-
"""
02_extension_qcew.py — 独立扩展：用 BLS QCEW 官方数据做县层面 DiD。

思路：把 Card-Krueger(1994) 的门店级电话调查，换成 BLS 的行政工资记录(QCEW/ES-202)
的县级汇总，检验 1992 年 4 月 NJ 最低工资上调是否导致 NJ 县"餐饮业"(SIC 58)就业
相对 PA 县下降。

输入：data/raw/sic_1992_qtrly_by_area.zip（BLS QCEW，SIC 分类 1975-2000）
输出：results/tables/extension_did.csv、results/figures/extension_employment_change.png
运行：python code/02_extension_qcew.py
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
# 稳健性检验：Card & Krueger (1994) 电话调查覆盖的 7 个东部 PA 县，作为更可比的对照组
EAST_PA_FIPS = {"42017", "42029", "42069", "42077", "42079", "42091", "42095"}
KEEP_COLS = ["own_code", "industry_code", "agglvl_code", "year", "qtr",
             "disclosure_code", "qtrly_estabs_count",
             "month1_emplvl", "month2_emplvl", "month3_emplvl",
             "total_qtrly_wages", "avg_wkly_wage"]


def load_county_files():
    """从 zip 里定位 NJ(34xxx)/PA(42xxx) 的县文件。"""
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
    """读入并筛选：餐饮业(SIC 58/581/5810) × 私营(own_code=5) 的县×季度面板。"""
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
    """构造县层面 DiD：before=2月+3月，after=11月+12月，dlog=对数变化。"""
    q1 = df[df["qtr"] == 1].set_index("fips")
    q4 = df[df["qtr"] == 4].set_index("fips")
    before = (q1["month2_emplvl"] + q1["month3_emplvl"]) / 2.0   # 2月+3月
    after = (q4["month2_emplvl"] + q4["month3_emplvl"]) / 2.0    # 11月+12月
    d = pd.DataFrame({"state": q1["state"], "before": before, "after": after}).dropna()
    d["dlog"] = np.log(d["after"]) - np.log(d["before"])
    d["nj"] = (d["state"] == "34").astype(int)
    return d


def _wide(df, outcome, full_quarter):
    """把 县×季度 面板转成 县级 before/after 对数变化。

    outcome: "employment"(就业) 或 "establishments"(机构数)。
    full_quarter: True 用全季度(1+2+3月 / 10+11+12月)，False 用 2-3月 / 11-12月。
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
    else:  # establishments（机构数本身就是季度值）
        before = q1["qtrly_estabs_count"]
        after = q4["qtrly_estabs_count"]
    d = pd.DataFrame({"fips": q1.index, "state": q1["state"],
                      "before": before, "after": after}).dropna()
    d["dlog"] = np.log(d["after"]) - np.log(d["before"])
    d["nj"] = (d["state"] == "34").astype(int)
    return d


def _did(d):
    """对县级数据跑 DiD 回归，返回 (系数, 标准误, t, p, n)。"""
    X = sm.add_constant(d[["nj"]])
    fit = sm.OLS(d["dlog"], X).fit()
    return fit.params["nj"], fit.bse["nj"], fit.tvalues["nj"], fit.pvalues["nj"], int(fit.nobs)


def robustness(df):
    """稳健性检验：换对照组 / 换窗口 / 换结果变量。"""
    rows = []
    d = _wide(df, "employment", full_quarter=False)
    rows.append(("1. 主设定：就业 2-3月 vs 11-12月，全 PA", *_did(d)))

    d2 = d[d["fips"].str[:2].eq("34") | d["fips"].isin(EAST_PA_FIPS)].copy()
    rows.append(("2. 对照组换成东部 PA（7 县）", *_did(d2)))

    d3 = _wide(df, "employment", full_quarter=True)
    rows.append(("3. 全季度窗口 Q1 vs Q4", *_did(d3)))

    d4 = _wide(df, "establishments", full_quarter=False)
    rows.append(("4. 结果变量换成机构数", *_did(d4)))

    return pd.DataFrame(rows, columns=["稳健性检验", "DiD系数", "标准误", "t值", "p值", "样本量"])


def main():
    county_files = load_county_files()
    print(f"县文件：NJ {sum(1 for f,_ in county_files if f.startswith('34'))} 个，"
          f"PA {sum(1 for f,_ in county_files if f.startswith('42'))} 个")

    df = build_panel(county_files)
    d = build_did(df)
    print(f"县层面样本：{len(d)} 个县（NJ {int(d.nj.sum())}，PA {int((1-d.nj).sum())}）")

    # 保存处理后的县层面面板
    PROC = Path("data/processed")
    PROC.mkdir(parents=True, exist_ok=True)
    d.to_csv(PROC / "qcew_county_panel.csv")
    print("处理后数据已保存 →", PROC / "qcew_county_panel.csv")

    # DiD 均值表
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
    print("\nDiD 均值表已保存 →", OUT_TAB / "extension_did.csv")
    print(tab.round(4))

    print(f"\nDiD 回归：dlog ~ NJ")
    print(f"  系数={fit.params['nj']:+.4f}  SE={fit.bse['nj']:.4f}  "
          f"t={fit.tvalues['nj']:.3f}  p={fit.pvalues['nj']:.3f}  n={int(fit.nobs)}")

    # 就业变化分布图（叠加各组均值参考线与 DiD 标注）
    fig, ax = plt.subplots(figsize=(8, 4.5))
    bins = np.linspace(d["dlog"].min() - 0.02, d["dlog"].max() + 0.02, 18)
    ax.hist(d.loc[d.nj == 1, "dlog"], bins=bins, alpha=0.55, color="tab:blue",
            label="New Jersey (treated)", edgecolor="white")
    ax.hist(d.loc[d.nj == 0, "dlog"], bins=bins, alpha=0.55, color="tab:orange",
            label="Pennsylvania (control)", edgecolor="white")
    ax.axvline(0, color="gray", linewidth=0.8)
    # 各组均值参考线（虚线）
    ax.axvline(dlog_nj, color="tab:blue", linestyle="--", linewidth=1.2)
    ax.axvline(dlog_pa, color="tab:orange", linestyle="--", linewidth=1.2)
    # DiD 估计量与显著性标注
    ax.text(0.98, 0.96,
            f"DiD = {did:+.3f}  (t = {fit.tvalues['nj']:.2f}, p = {fit.pvalues['nj']:.2f}, n = {int(fit.nobs)})",
            transform=ax.transAxes, ha="right", va="top",
            bbox=dict(boxstyle="round", fc="white", ec="0.8"))
    ax.set(xlabel="Log change in Eating & Drinking Places employment",
           ylabel="Number of counties",
           title="1992 change in Eating & Drinking Places employment: NJ vs PA counties (QCEW)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT_FIG / "extension_employment_change.png", dpi=150)
    plt.close(fig)
    print("扩展图已保存 →", OUT_FIG / "extension_employment_change.png")

    # 稳健性检验
    rob = robustness(df)
    rob.to_csv(OUT_TAB / "extension_robustness.csv")
    print("\n稳健性检验已保存 →", OUT_TAB / "extension_robustness.csv")
    print(rob.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
