# Screening (step 0): candidate list and NeuralFoil screening at lambda 5.4

Step 0a builds the candidate list from the UIUC airfoil database; step 0b screens every candidate
with NeuralFoil polars and the same BEM design and analysis as the XFOIL study; the top 5 go on to the
XFOIL check (`config.yaml` reads them from `results/screen_ranking.csv`). `reproduce.bat` in the
repository folder runs all of it.

## Files
| File | What |
|---|---|
| `00_build_list.py` | step 0a: UIUC set in AeroSandbox 4.2.10 (2174 airfoils) → candidates. Keeps 12.5 % ≤ t/c ≤ 25 % and Cl at max L/D at or below the 40 mm tip chord ceiling for at least one λ in 4.5 to 6.5 (NeuralFoil, tip Re). Settings at the top of the script |
| `00_screen.py` | step 0b: NeuralFoil polars, then the same design and BEM code as steps 02 and 03 (`bem.py`, `config.yaml`) |
| `plot_screen.py` | report figures |
| `parse_list.py` | reads candidate lists (the text format below, a plain list of names, or a CSV) |
| `reference/foil_list_676.txt` | the original candidate list from the first (cloud) study. Not used by the chain; `00_build_list.py` compares its result with it |
| `reference/compare_with_original.csv` | this screening against the original screening table from the cloud study (status doc Part 3) |
| `results/candidates_uiuc.txt`, `.csv` | the candidate list made by `00_build_list.py` |
| `results/screen_designs.csv` | every design (airfoil x alpha offset), 8390 rows |
| `results/screen_ranking.csv` | best offset per airfoil, ranked by Cp at lambda 5.4 with tip loss |
| `results/fig_*.png` | top 20, distribution of all airfoils, Cp vs alpha offset heatmap |

## Run (Windows, from the repository folder)
```
.venv\Scripts\python screening\00_build_list.py
.venv\Scripts\python screening\00_screen.py
.venv\Scripts\python screening\plot_screen.py
```
The list takes under a minute, the screening about 7 min on 2 cores. NeuralFoil polars are cached in
`results/polars/` (shared by all lists); delete that folder to recompute.

`00_build_list.py` gives the same 676 airfoils with the same t/c as the original list, so the
screening result is the same. Only the λ block of 11 borderline airfoils (Cl within 0.01 of a ceiling)
differs; the screening uses the names and t/c, not the block.

## Screen your own list
Give the list with `--list` (by default `00_screen.py` reads `results/candidates_uiuc.txt`). Use `--out` so the report results in `results/` are not overwritten:
```
.venv\Scripts\python screening\00_screen.py --list my_list.txt --out screening\results_my_list
.venv\Scripts\python screening\plot_screen.py --out screening\results_my_list
```
The list can be:

* **The same format as `results/candidates_uiuc.txt`**: blocks starting with a line like
  `λ=5.0 (Cl≤1.26, Re≈193k), 262 airfoils:` and the airfoils on the next line as
  `name t/c%/LDmax/Cl/alpha; name ...`. The number of airfoils in the block line must match.
* **A plain text file**, one name per line, optionally with t/c in %:
  ```
  # my candidates
  mh114
  e396 13.1
  ```
  Without t/c it is measured from the geometry.
* **A CSV** with a column `name` (and optionally `tc` in %).

Names are the UIUC names in AeroSandbox 4.2.10, the same as on airfoiltools.com without `-il`
(airfoiltools `mh114-il` is `mh114`). A misspelled name stops the run with a list of the unknown
names. The list as read is saved as `candidates.csv` in the output folder.

The design settings (λ, α offsets, constraints) come from `config.yaml`, the same as the XFOIL study.
To screen at another λ, change `design.lambdas` there (and change it back for the λ 5.4 study).

To send the winners on to the XFOIL check: put their `.dat` files in `airfoils/` and their names under
`airfoils:` in `config.yaml`, then run `run_all.bat`.

## Settings
- Geometry: UIUC set bundled with AeroSandbox 4.2.10.
- Polars (step 0b): NeuralFoil 0.3.3, model `large`, Ncrit 5, alpha -5..20 deg in 0.25 deg steps.
  The candidate list (step 0a) uses alpha -5..15 deg and the tip Re of each λ, see `00_build_list.py`.
- Design: NeuralFoil evaluated at the exact Re of each Re iteration step (r/R = 0.7, tol 30 000).
  Off-design BEM: polars on Re 60k..320k (20k steps), bilinear lookup, as in 03_performance.py.
- alpha_des = alpha_opt + offset, +2 .. -4 deg in 0.5 deg steps; realistic blade and constraints as in
  step 03; ranking by Cp at lambda 5.4 with Prandtl tip loss + Buhl.

## Result
Compared with the original screening from the cloud study (`reference/compare_with_original.csv`):
same winner and same top 5 as the original screening: mh114 (Cp 0.4530, alpha_des 3.75 deg,
alpha_opt 4.25 deg), e396 (0.4527), then e397, goe497 and goe501 within 0.0001 of each other.
Cp values are within 0.0003 of the original. 14 of the original top 15 are in the new top 15.

Differences from the original run:
- All 676 airfoils are screened here. The original prescreened 109 first; that rule was not recorded.
  Five airfoils give no valid design (c141a, l1003, naca16015, naca16018, naca16021), so 671 are ranked.
- Ranks 3 to 5 swap order (e397 3rd here, goe497 3rd originally). The gap is 0.0001 in Cp.
- e68 is 19th here (16th originally), because three airfoils outside the original 109 rank above it
  (fx62k131, e399, fx84w140).
- e396 lands on alpha_opt 6.00 here (6.25 originally), from small Re differences in the iteration.
