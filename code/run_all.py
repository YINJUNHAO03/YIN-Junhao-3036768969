# -*- coding: utf-8 -*-
"""
run_all.py — 一键入口：先跑主复现(表2~4、图1)，再跑 QCEW 扩展，生成全部表和图。

前提：把原始数据放进 data/raw/ 后，直接运行即可，无需改任何代码：
    data/raw/public.csv
    data/raw/sic_1992_qtrly_by_area.zip

运行：python code/run_all.py
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent


def run(script):
    print("=" * 70)
    print(f"运行 {script}")
    print("=" * 70)
    r = subprocess.run([sys.executable, str(HERE / script)])
    if r.returncode != 0:
        print(f"\n[失败] {script} 返回码 {r.returncode}")
        sys.exit(r.returncode)
    print()


def main():
    run("01_replicate_main.py")
    run("02_extension_qcew.py")
    print("完成。所有表和图已写入 results/tables/ 与 results/figures/。")


if __name__ == "__main__":
    main()
