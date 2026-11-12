"""Step 0: NeuralFoil screening of all candidate airfoils at the fixed design lambda (5.4).

Rebuilds the cloud screening that picked the top 5 for the XFOIL check (Part 3 in the status doc).
It uses the same design and analysis code as steps 02 and 03 (bem.py, config.yaml); only the polar
source differs: NeuralFoil instead of XFOIL.

Per airfoil:
  1. Geometry from the UIUC set bundled with AeroSandbox 4.2.10 (asb.Airfoil(name)).
  2. Polars from NeuralFoil 0.3.3 (model "large", Ncrit 5) on the RE_LIST x ALPHA grid below.
     No convergence problems, so every point is kept. Extended to 360 deg with Viterna (bem.py).
  3. For every offset alpha_des = alpha_opt + offset (config.yaml design: +2 .. -4 deg, 0.5 steps):
     Re iteration at r/R = 0.7 and BEM design without tip loss (02_design.py).
  4. Realistic blade: root cut, 48 mm cylinder, chord clamped to 40..100 mm, t_max >= 5 mm checked
     (03_performance.py).
  5. Steady BEM with Prandtl tip loss + Buhl for lambda 2..10 (config.yaml performance).
Each airfoil keeps the offset with the highest Cp at lambda_des with tip loss among designs that meet
all constraints; airfoils are then ranked by that Cp (ties by CL/CD), as in 03_performance.py.

Run from the wind_blade folder (needs: pip install aerosandbox==4.2.10 neuralfoil==0.3.3):
    .venv\\Scripts\\python screening\\00_screen.py
Reads : config.yaml, screening/foil_list_676.csv
Writes: screening/results/screen_designs.csv   every design (airfoil x offset)
        screening/results/screen_ranking.csv   best design per airfoil, ranked
        screening/results/polars/<name>.csv    NeuralFoil polars (cache; delete to recompute)
"""
from __future__ import annotations

import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import bem  # noqa: E402

# ---------------------------------------------------------------- screening settings
LIST_FILE = HERE / "foil_list_676.csv"
OUT = HERE / "results"
NCRIT = 5
MODEL_SIZE = "large"                                   # NeuralFoil default; reproduces the list values
RE_LIST = np.arange(60_000, 320_001, 20_000)           # 60k .. 320k
ALPHA = np.arange(-5.0, 20.0001, 0.25)                 # deg
WORKERS = min(8, os.cpu_count() or 4)


def neuralfoil_polars(name: str) -> dict:
    """Re -> DataFrame(alpha, CL, CD), cached as one CSV per airfoil."""
    f = OUT / "polars" / f"{name}.csv"
    if f.exists():
        df = pd.read_csv(f)
    else:
        import aerosandbox as asb
        import neuralfoil as nf
        af = asb.Airfoil(name)
        rows = []
        for re in RE_LIST:
            a = nf.get_aero_from_airfoil(af, alpha=ALPHA, Re=float(re), n_crit=NCRIT, model_size=MODEL_SIZE)
            rows.append(pd.DataFrame(dict(Re=float(re), alpha=ALPHA, CL=a["CL"], CD=a["CD"],
                                          CM=a["CM"], conf=a["analysis_confidence"])))
        df = pd.concat(rows)
        df.to_csv(f, index=False)
    return {float(re): g[["alpha", "CL", "CD"]].reset_index(drop=True) for re, g in df.groupby("Re")}


class NFPolarSet(bem.PolarSet):
    """PolarSet whose design lookup calls NeuralFoil at the exact Re of each Re iteration step
    (NeuralFoil works at any Re, so no interpolation between Re polars is needed in the design step).
    The off-design BEM still uses the RE_LIST grid with bilinear lookup, as in 03_performance.py."""

    def design_props(self, re: float, offset: float) -> dict | None:
        import neuralfoil as nf
        key = round(float(re))
        if key not in self._cache:
            a = nf.get_aero_from_airfoil(self._af, alpha=ALPHA, Re=float(key), n_crit=NCRIT, model_size=MODEL_SIZE)
            self._cache[key] = pd.DataFrame(dict(alpha=ALPHA, CL=a["CL"], CD=a["CD"]))
        return bem.alpha_opt_props(self._cache[key], offset)


def screen_airfoil(args) -> list[dict]:
    import aerosandbox as asb
    name, tc = args
    cfg = bem.load_config()
    dcfg, pf = cfg["design"], cfg["performance"]
    pol = NFPolarSet.from_raw(name, neuralfoil_polars(name), cfg)
    pol._af, pol._cache = asb.Airfoil(name), {}
    st = dcfg["alpha_offsets_step"]
    offsets = np.round(np.arange(dcfg["alpha_offset_max"], dcfg["alpha_offset_min"] - st / 2, -st), 3)
    lams = np.round(np.arange(pf["lambda_min"], pf["lambda_max"] + 1e-9, pf["lambda_step"]), 3)
    rows = []
    for lam in dcfg["lambdas"]:
        i_des = int(np.argmin(np.abs(lams - lam)))
        for off in offsets:
            conv = bem.converge_re(pol, lam, float(off), cfg)
            if conv is None:
                continue
            design = bem.design_blade(lam, conv, cfg)
            blade, info = bem.realistic_blade(design, tc, cfg)
            pan = bem.panels(blade, pf["n_panels"], cfg["rotor"]["R"], cfg["rotor"]["r_hub"])
            out = bem.bem_sweep(pan, pol, lams, cfg, tip_loss=True)
            s = bem.summarise(out, pf["plateau_frac"])
            rows.append(dict(airfoil=name, tc_pct=tc * 100, lambda_des=lam, alpha_offset=float(off),
                             alpha_opt=conv["alpha_opt"], alpha_des=conv["alpha_des"], CL=conv["CL"],
                             CD=conv["CD"], CL_CD=conv["LD"], Re_des=conv["re_conv"],
                             Cp_at_lam_des_TL=float(out["Cp"][i_des]), Ct_at_lam_des_TL=float(out["Ct"][i_des]),
                             Cp_max_TL=s["Cp_max"], lam_Cp_max_TL=s["lam_at_Cp_max"],
                             plateau_width_TL=s["plateau_width"], **info))
    return rows


def main():
    (OUT / "polars").mkdir(parents=True, exist_ok=True)
    foils = pd.read_csv(LIST_FILE)
    jobs = [(r.name, r.tc / 100) for r in foils.itertuples()]
    t0, rows = time.time(), []
    with ProcessPoolExecutor(WORKERS) as ex:
        for k, res in enumerate(ex.map(screen_airfoil, jobs, chunksize=4), 1):
            rows += res
            if k % 50 == 0 or k == len(jobs):
                print(f"{k}/{len(jobs)} airfoils  ({time.time() - t0:.0f} s)", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "screen_designs.csv", index=False)

    ok = df[df.constraints_ok]
    best = (ok.sort_values(["Cp_at_lam_des_TL", "CL_CD"], ascending=False)
              .groupby("airfoil", sort=False).head(1).reset_index(drop=True))
    best.insert(0, "rank", np.arange(1, len(best) + 1))
    best = best.merge(foils[["name", "list_lambda", "LDmax"]].rename(columns={"name": "airfoil",
                      "LDmax": "LDmax_list"}), on="airfoil", how="left")
    best.to_csv(OUT / "screen_ranking.csv", index=False)
    print(f"{len(df)} designs, {len(ok)} meet all constraints, {len(best)} airfoils ranked")
    print(best.head(20)[["rank", "airfoil", "tc_pct", "alpha_opt", "alpha_des", "CL", "CL_CD",
                         "Cp_at_lam_des_TL", "lam_Cp_max_TL", "n_clamped_min", "n_clamped_max",
                         "t_min_mm"]].to_string(index=False, float_format="%.4g"))


if __name__ == "__main__":
    main()
