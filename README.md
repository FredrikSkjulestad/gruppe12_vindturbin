# wind_blade

Blade design code for the TEP4175 group project (NTNU, fall 2026). It finds the airfoil, design tip speed ratio (λ_des) and design angle of attack (α_des) that give the highest realistic C_P under the production constraints: chord 40 to 100 mm, t_max ≥ 5 mm, Z = 2, R = 0.45 m, r_hub = 0.03 m.

This repository holds one of the two blade models in the group report (the Python/XFOIL model). The other subgroup's model is not included.

## Where the report numbers come from

| Report content | Code | Settings | Output |
|---|---|---|---|
| Airfoil screening at λ 5.4 (676 candidates, NeuralFoil) | `screening/00_screen.py`, `screening/plot_screen.py` | `config.yaml` (design and BEM) + settings in `screening/README.md` | `screening/results/` |
| XFOIL check of the top 5 at λ 5.4, final blade (mh114) | `run_all.bat` (steps 01 to 05) | `config.yaml` | `results_lambda54/` |
| Earlier λ sweep 5.0 to 6.5, 20 airfoils (best: e68 at λ 6.5) | `run_sweep.bat` (steps 01 to 05) | `config_sweep.yaml` | `results/` |
| Code verification against Assignments 3 and 4 | `validation/validate_goe227.py` | `config.yaml` (rotor only) | `validation/output/` |
| QBlade cross-check | QBlade CE 2.0.9.7, by hand | blade and polars from `results_lambda54/report/winner/` | `qblade/` |

The key numbers for the final blade are in `results_lambda54/report/sanity_checks.txt`. The method follows the method note `docs/BEM_metodenotat.pdf`; `bem.py` tags each equation with its source.

## 1. Install Python (Windows, winget)

Any Python 3.12 or 3.13 works (all pinned packages have wheels for both). In PowerShell **as administrator** (machine scope installs for all users):

```powershell
winget install --id Python.Python.3.12 --exact --version 3.12.10 --scope machine --silent --accept-package-agreements --accept-source-agreements
```

Close and reopen PowerShell, then check that `py -3.12 --version` prints `Python 3.12.10`. (The results in this repository were made with Python 3.13.15, winget ID `Python.Python.3.13`.)

## 2. Python packages (pinned)

From this folder:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If activation is blocked, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once. The screening step needs two more packages:

```powershell
.\.venv\Scripts\python -m pip install aerosandbox==4.2.10 neuralfoil==0.3.3
```

## 3. XFOIL

XFOIL is not included in this repository and has no winget package:

1. Download XFOIL 6.99 for Windows from the MIT XFOIL page: https://web.mit.edu/drela/Public/web/xfoil/ (file `XFOIL6.99.zip`).
2. Unzip it and put `xfoil.exe` in `bin\xfoil.exe`. The file used for the results has SHA256 `C17342F84AE260C2B11A74CD0E2FB8189A5F8954C6BB7A8467A0F27055C7FAEA`.
3. The path is set in `config.yaml` (`paths.xfoil`). It is relative to this folder, or an absolute path like `C:/tools/xfoil/xfoil.exe`.

Every XFOIL call has a timeout (`xfoil.timeout_s`), so one hanging case cannot stop the run. Graphics are switched off in the XFOIL batch input, so no XFOIL windows pop up.

## 4. Run

| Study | Command | Settings | Results |
|---|---|---|---|
| λ 5.4 study (final blade) | double click `run_all.bat` | `config.yaml` | `results_lambda54/` |
| Earlier λ sweep | double click `run_sweep.bat` | `config_sweep.yaml` | `results/` |
| Screening | `.venv\Scripts\python screening\00_screen.py` then `screening\plot_screen.py` | see `screening/README.md` | `screening/results/` |
| Code check | `.venv\Scripts\python validation\validate_goe227.py` | | `validation/output/` |

Both batch files run the same five scripts. `run_sweep.bat` only sets the environment variable `WIND_BLADE_CONFIG=config_sweep.yaml` first; `bem.load_config()` reads that file instead of `config.yaml`. To run a single step of the sweep by hand:

```powershell
$env:WIND_BLADE_CONFIG = "config_sweep.yaml"
.\.venv\Scripts\python.exe 03_performance.py
Remove-Item Env:WIND_BLADE_CONFIG
```

In VS Code, *Run and Debug* has one entry per step (`.vscode/launch.json`); these use `config.yaml`.

| Script | Does | Main output (in the results folder) |
|---|---|---|
| `01_polars.py` | XFOIL polars, every airfoil × 11 Re (−5° to 20°, 0.5° steps, Ncrit 5), reliability flags, Viterna 360° extrapolation | `polars/`, `01_polars_summary.csv` |
| `02_design.py` | Assignment 3 design for every airfoil × λ_des × α_des | `designs/`, `02_design_summary.csv` |
| `03_performance.py` | Assignment 4 blade (root cut, cylinder, tip, clamp 40 to 100 mm, thickness check), BEM over λ = 2 to 10 with and without tip loss, ranking | `blades/`, `performance/`, `03_performance_summary.csv` |
| `04_report.py` | Results table, heatmap, top 3 plots, winner export for QBlade, sanity checks | `report/` |
| `05_plots.py` | Plots of the best designs in the style of Assignments 1, 3 and 4. Shows the figures in windows at the end; close them to finish, or run with `--no-show` | `plots/` |
| `explore.ipynb` | Plot any design from the CSVs | |

Each step reads the CSV output of the step before, so any step can be rerun on its own. XFOIL polars are cached in `cache/polars`, keyed by the coordinates and the XFOIL settings, so a polar is only recomputed when one of those changes. Delete `cache/` to force a full rerun. Runtimes on a 2 core machine: step 01 about 5 min, step 02 20 s, step 03 3 min, step 04 10 s.

## 5. Method and deviations from the assignments

| Item | Source | Note |
|---|---|---|
| Blade elements r_i = (i − ½)dr, N = 15 | A3 4.1, method note 7 | N = 15 puts one element centre at r/R = 0.700 |
| Re iteration at r/R = 0.7, tol 30 000, values locked from the last pass | A3 4.3 flow chart | Reproduces 208 290 → 145 160 → 136 621 exactly with the Assignment 3 QBlade polars |
| Cubic for a, a′, φ (atan2), C_a, L_c/R, θ = φ − α_des | A3 4.4 flow chart, method note 5 | No tip loss in the design, as in A3 |
| α_des = α_opt(Re) + offset | Added | λ 5.4 study: offsets +2 to −4° in 0.5° steps. Sweep: 0, −0.5, … until C_L/C_D is 10 % below its max. The offset stays fixed while Re is iterated |
| Root cut r < r_hub, cylinder 48 mm with θ = 0 at r_hub, tip station copying the last element | A4 Table 3 | |
| Chord clamped to 40 to 100 mm, twist kept, t = (t/c)·c ≥ 5 mm | A4 Table 4 | |
| Off-design BEM with Prandtl F, Buhl correction for a > 0.4 | **Not in the course documents** (A4 used QBlade). Hansen, *Aerodynamics of Wind Turbines* ch. 6; Buhl 2005 | Validated against the Assignment 4 QBlade run (below) |
| Polars between stations blended linearly, 40 cosine spaced panels | Chosen to match QBlade | |
| Cylinder C_L = 0, C_D = 1.2 | Assumption | `config.yaml` → `realistic` |
| Viterna: C_D,max = 1.11 + 0.018·AR, AR = 8.4; back side C_L × 0.7 | A1 names the method; formulas from Viterna and Corrigan 1982 | |
| μ = 1.47e-5 | A3 Table 2 | Numerically this is ν. Used as given, as in the method note |
| Ranking | | λ 5.4 study: C_P at λ 5.4 with tip loss (`Cp_at_lam_des_TL`). Sweep: highest C_P anywhere on the curve with tip loss (`Cp_max_TL`) |

**Validation** (`validation/validate_goe227.py`): runs `bem.py` on the GOE 227 blade from Assignments 3 and 4 with the same polars QBlade used. GOE 227 is only a code check and is not part of the study.

* **Assignment 3:** Re history, α_opt 6.00°, C_L 1.4770, C_D 0.0207, C_P 0.5245 and C_T 0.8847 are all reproduced. Chord and twist match to 0.01 mm and 0.01°.
* **Assignment 4:** QBlade gave C_P,max 0.427 at λ 5.6 (tip loss) and 0.480 at λ 5.4 (no tip loss). `bem.py` gives 0.436 at 5.6 and 0.487 at 5.5.

## 6. Using the winner in QBlade

`results_lambda54/report/winner/` contains:

| File | Content |
|---|---|
| `winning_blade.csv` | r, r − r_hub, chord, twist, airfoil for every station |
| `<airfoil>.dat` | Clean coordinates. Import with *Airfoil → Import* |
| `Polars/*_N5.txt` | Raw XFOIL polars per Re. Import with *Polar → Import XFoil polar* |
| `Polars/*_360_V.plr` | 360° polars in QBlade's .plr layout |
| `Polars/circular_360.plr` | The root cylinder |
| `<design_id>.bld` | Blade file in the layout of the Assignment 3 rotor file |
| `qblade/` | The same files in QBlade's folder layout |

`qblade/` in the repository root holds the QBlade projects used for the cross-check: `mh114_lambda54.qpr` (final blade, λ 5.4) and `e68_winner.qpr` (best blade from the λ sweep). For other airfoils, use the cleaned unit chord files in `<results>/airfoils_clean/` (Selig format).

## 7. Folder

```
wind_blade/
  config.yaml            λ 5.4 study: all parameters, airfoil list, path to xfoil.exe
  config_sweep.yaml      earlier λ sweep (same file, lines marked SWEEP differ)
  run_all.bat            λ 5.4 study, steps 01 to 05
  run_sweep.bat          λ sweep, steps 01 to 05
  01_polars.py  02_design.py  03_performance.py  04_report.py  05_plots.py
  bem.py                 shared BEM functions (each equation tagged with its source)
  xfoil_runner.py        shared XFOIL functions (geometry, batch runs, cache)
  explore.ipynb
  airfoils/              original .dat files + SOURCES.csv (download URL for every file)
  screening/             NeuralFoil screening of the 676 candidates (own README)
  validation/            QBlade reference data from A3/A4 and the check script
  results_lambda54/      results of the λ 5.4 study
  results/               results of the λ sweep
  qblade/                QBlade projects for the cross-check
  docs/                  method note
  bin/                   put xfoil.exe here
```

## Sources and licence

* Airfoil coordinates: UIUC Airfoil Coordinates Database, via airfoiltools.com. Three airfoils (`sb96d_13_3`, `hn975ta`, `mid403`) come from the UIUC set shipped with AeroSandbox v4.2.10. The URL for every file is in `airfoils/SOURCES.csv`.
* XFOIL 6.99 (M. Drela, MIT, GPL) is used but not distributed here.
* NeuralFoil 0.3.3 and AeroSandbox 4.2.10 (P. Sharpe) are used for the screening.
* Code: MIT licence, see `LICENSE`.
