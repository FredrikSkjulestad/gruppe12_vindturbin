# Screening (step 0): NeuralFoil at lambda 5.4

Rebuild of the cloud screening that picked the five airfoils for the XFOIL check (status doc Part 3).
Rebuilt 2026-11-02 from the original candidate list; the original screening code was not saved.

## Files
| File | What |
|---|---|
| `foil_list_676.txt` | the 676 candidates (UIUC, 12.5 % <= t/c <= 25 %) as the original NeuralFoil list: the header says how it was made, then one block per λ with t/c, L/D max, Cl at L/D max and α_opt for each airfoil |
| `parse_list.py` | reads a candidate list (this format, a plain list of names, or a CSV) |
| `00_screen.py` | screening: NeuralFoil polars, then the same design and BEM code as steps 02 and 03 (`bem.py`, `config.yaml`) |
| `plot_screen.py` | report figures |
| `results/screen_designs.csv` | every design (airfoil x alpha offset), 8390 rows |
| `results/screen_ranking.csv` | best offset per airfoil, ranked by Cp at lambda 5.4 with tip loss |
| `results/compare_with_original.csv` | this run against the original screening table |
| `results/fig_*.png` | top 20, distribution of all airfoils, Cp vs alpha offset heatmap |

## Run (Windows, from the repository folder)
```
.venv\Scripts\python -m pip install aerosandbox==4.2.10 neuralfoil==0.3.3
.venv\Scripts\python screening\00_screen.py
.venv\Scripts\python screening\plot_screen.py
```
This screens `foil_list_676.txt`. About 7 min on 2 cores. Polars are cached in `results/polars/`
(shared by all lists); delete that folder to recompute.

## Screen your own list
Give the list with `--list`. Use `--out` so the report results in `results/` are not overwritten:
```
.venv\Scripts\python screening\00_screen.py --list my_list.txt --out screening\results_my_list
.venv\Scripts\python screening\plot_screen.py --out screening\results_my_list
```
The list can be:

* **The same format as `foil_list_676.txt`**: blocks starting with a line like
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
- Polars: NeuralFoil 0.3.3, model `large`, Ncrit 5, alpha -5..20 deg in 0.25 deg steps. These settings
  reproduce the L/D max, Cl and alpha_opt in the original list.
- Design: NeuralFoil evaluated at the exact Re of each Re iteration step (r/R = 0.7, tol 30 000).
  Off-design BEM: polars on Re 60k..320k (20k steps), bilinear lookup, as in 03_performance.py.
- alpha_des = alpha_opt + offset, +2 .. -4 deg in 0.5 deg steps; realistic blade and constraints as in
  step 03; ranking by Cp at lambda 5.4 with Prandtl tip loss + Buhl.

## Result
Same winner and same top 5 as the original screening: mh114 (Cp 0.4530, alpha_des 3.75 deg,
alpha_opt 4.25 deg), e396 (0.4527), then e397, goe497 and goe501 within 0.0001 of each other.
Cp values are within 0.0003 of the original. 14 of the original top 15 are in the new top 15.

Differences from the original run:
- All 676 airfoils are screened here. The original prescreened 109 first; that rule was not recorded.
  Five airfoils give no valid design (c141a, l1003, naca16015, naca16018, naca16021), so 671 are ranked.
- Ranks 3 to 5 swap order (e397 3rd here, goe497 3rd originally). The gap is 0.0001 in Cp.
- e68 is 19th here (16th originally), because three airfoils outside the original 109 rank above it
  (fx62k131, e399, fx84w140).
- e396 lands on alpha_opt 6.00 here (6.25 originally), from small Re differences in the iteration.
