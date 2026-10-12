# -*- coding: utf-8 -*-
"""
run_all.py — one-click entry point: runs the main replication (Tables 2-4 and
Figure 1), then the QCEW extension, generating all tables and figures.

Prerequisite: after placing the raw data in data/raw/, just run it directly with
no code changes:
    data/raw/public.csv
    data/raw/sic_1992_qtrly_by_area.zip

Run: python code/run_all.py
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent


def run(script):
    print("=" * 70)
    print(f"Running {script}")
    print("=" * 70)
    r = subprocess.run([sys.executable, str(HERE / script)])
    if r.returncode != 0:
        print(f"\n[Failed] {script} returned code {r.returncode}")
        sys.exit(r.returncode)
    print()


def main():
    run("01_replicate_main.py")
    run("02_extension_qcew.py")
    print("Done. All tables and figures written to results/tables/ and results/figures/.")


if __name__ == "__main__":
    main()
