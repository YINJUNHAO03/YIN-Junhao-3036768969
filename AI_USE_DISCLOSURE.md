# AI-Use Disclosure

This project used an AI coding assistant (Trae) throughout the workflow. This document records where AI was used, how its outputs were checked, and which suggestions were corrected or rejected.

## Where and how AI was used

1. **Data preparation and variable construction.** The assistant wrote the code that reads `public.csv`, handles missing values, and constructs FTE employment, the employment change `demp`, the wage gap `gap`, and related variables, following the paper's definitions.

2. **Replication of Tables 2–4 and Figure 1.** The assistant wrote the code that reproduces the tables and figure, and helped reconcile them with the published values.

3. **Independent extension.** The assistant helped locate the BLS QCEW data, designed the county-level DiD (SIC 58 employment, Feb–Mar vs Nov–Dec 1992), and wrote `02_extension_qcew.py`.

4. **Reproducibility packaging.** The assistant helped restructure the project into `code/`, `data/`, `results/`, `skills/`, and `report/`, and wrote `README.md` and this disclosure.

5. **Version control guidance.** The assistant explained the Git/GitHub workflow (init, commit, push, collaborators).

## How AI-generated code, analysis, and writing were checked

- **Numerical verification.** Every replicated number was checked against the paper. For example, the NJ/PA FTE means (20.44 / 23.33 / 21.03 / 21.17), the DiD (≈ 2.75), and the Table 4 coefficients (2.33, 2.30, 15.65, 14.92, 11.91) and sample size (357) all match the published values to reported precision.
- **Cross-check with the author's own code.** The variable definitions (FTE = full-time + managers + 0.5×part-time; the `gap` formula; the Table 4 column-(v) specification) were cross-checked against the `check.sas` program distributed with the data on David Card's website.
- **Manual inspection.** Intermediate tables (e.g., the DiD four-cell means) were manually recomputed and compared.

## Important AI errors or suggestions that were corrected or rejected

1. **Wrong column-specification for fixed-width data.** An early attempt read `public.dat` with contiguous widths instead of column ranges; the state variable came out entirely missing. This was corrected by switching to explicit column positions.

2. **Row 5 of Table 3 (temporarily-closed stores).** An initial version incorrectly set wave-2 employment to zero for *all* missing stores, rather than only the four temporarily-closed stores. This changed the NJ change from the published 0.23 to −0.32. It was corrected to follow the paper's note d exactly.

3. **Table 2 percentage variables.** An initial version multiplied the t-statistic by 100 along with the mean and standard error, producing absurd t-values (e.g., −72). The scaling was corrected so only the means and standard errors are in percent.

4. **"Fast food" vs. "Eating and Drinking Places".** The assistant initially described the QCEW extension as covering "fast food" or "eating places"; inspection of the data showed the public SIC file only reports SIC 58 (all eating and drinking places, including bars). The extension was re-scoped and the limitation documented honestly.

5. **Rejected suggestion.** The assistant suggested re-using the paper's own Table 5 robustness checks as the "independent extension." This was rejected because it is already in the paper; the QCEW county-level analysis was chosen instead as a genuinely new analysis.

All code was run end-to-end and the outputs were inspected before being committed.
