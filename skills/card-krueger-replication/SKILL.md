---
name: card-krueger-replication
description: Reproduce the main tables and figures of Card & Krueger (1994, AER) and run the QCEW county-level extension. Use when asked to regenerate results, verify a table/figure, or inspect this project's replication workflow.
---

# Card & Krueger (1994) replication skill

Reproduce the minimum-wage / fast-food employment analysis end-to-end and check
the outputs against the paper.

## Inputs (place in `data/raw/` before running)

- `public.csv` — Card & Krueger (1994) store-level survey (410 stores, 46 columns).
- `sic_1992_qtrly_by_area.zip` — BLS QCEW, SIC classification (1992), for the county-level extension.

## Steps

1. **Check inputs.** Confirm `data/raw/public.csv` and `data/raw/sic_1992_qtrly_by_area.zip` exist. If not, read `README.md` for the download instructions and stop.

2. **Run the full workflow.**
   ```
   python code/run_all.py
   ```
   This runs `01_replicate_main.py` (Tables 2-4 and Figure 1) and `02_extension_qcew.py` (county-level DiD).

3. **Verify the core numbers against the paper.**
   - Table 3: NJ wave-1 FTE ≈ 20.44, wave-2 ≈ 21.03; PA wave-1 ≈ 23.33, wave-2 ≈ 21.17; DiD ≈ 2.75 (t ≈ 2.03).
   - Table 4: NJ dummy coefficient ≈ 2.33 (1.19); GAP ≈ 15.65 (6.08), with controls ≈ 14.92 (6.21), with region ≈ 11.91 (7.39); sample = 357 stores.
   - Figure 1: wave-1 wage distributions overlap across states; wave-2 NJ shifts to $5.05.

4. **Report where you put each output.** Tables go to `results/tables/`, figures to `results/figures/`.

5. **Keep data unchanged.** Do not edit files under `data/raw/`.

## Key definitions (for reference)

- FTE employment = full-time + managers + 0.5 × part-time.
- `demp` = wave-2 FTE − wave-1 FTE (change in employment).
- `gap` = proportional wage increase needed to reach the new $5.05 minimum (0 for PA and for NJ stores already at/above $5.05).
- Extension outcome = log change in county "Eating and Drinking Places" (SIC 58) employment, Feb–Mar vs Nov–Dec 1992.
