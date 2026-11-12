"""Step 2 (replaces Assignment 1): XFOIL polars for the shortlist + 360 deg Viterna extrapolation.

Reads : config.yaml, airfoils/*.dat
Writes: results/airfoils_clean/<name>.dat      unit-chord Selig files (XFOIL and QBlade)
        results/polars/<name>/raw_Re<Re>.csv    converged XFOIL points only (no interpolation across stall)
        results/polars/<name>/p360_Re<Re>.csv   Viterna 360 deg polar on a uniform alpha grid
        results/01_polars_summary.csv           one row per (airfoil, Re) with reliability flags
        results/01_airfoils.csv                 t/c, camber per airfoil
XFOIL results are cached in cache/polars and only rerun if coordinates or XFOIL settings change.
"""
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd

import bem
from xfoil_runner import cached_polar, read_coords, thickness, write_clean_dat


def flags(df: pd.DataFrame, n_expected: int, rel: dict) -> dict:
    """Reliability checks on one converged polar."""
    out = dict(n_points=len(df), conv_rate=len(df) / n_expected)
    p = bem.alpha_opt_props(df, 0.0)
    if p is None:
        out.update(flag="no usable polar")
        return out
    out.update(alpha_opt=p["alpha_opt"], CL_opt=p["CL"], CD_opt=p["CD"], LDmax=p["LDmax"],
               CL_max=float(df.CL.max()), alpha_CLmax=float(df.alpha[df.CL.idxmax()]))
    f = []
    a = df.alpha.values
    near = (a >= p["alpha_opt"] - 3) & (a <= p["alpha_opt"] + 3)
    gaps = np.diff(a[near]) if near.sum() > 1 else np.array([])
    if len(gaps) and gaps.max() > rel["gap_deg"] + 1e-9:
        f.append(f"gap {gaps.max():.1f} deg near alpha_opt")
    pre = df[df.alpha <= out["alpha_CLmax"]]
    dcl = np.diff(pre.CL.values) / np.maximum(np.diff(pre.alpha.values) / 0.5, 1)
    if len(dcl) and np.abs(dcl).max() > rel["jump_dcl"]:
        f.append(f"CL jump {np.abs(dcl).max():.2f} per 0.5 deg (laminar bubble?)")
    if out["conv_rate"] < rel["min_conv"]:
        f.append(f"convergence {out['conv_rate']:.0%}")
    out["flag"] = "; ".join(f)
    return out


def main():
    cfg = bem.load_config()
    P, xs = cfg["paths"], cfg["xfoil"]
    xfoil = str(P["xfoil"])
    res_dir = P["results"]
    clean_dir = res_dir / "airfoils_clean"
    geo = []
    for name in cfg["airfoils"]:
        dat = write_clean_dat(P["airfoils"] / f"{name}.dat", clean_dir / f"{name}.dat", name)
        g = thickness(read_coords(dat)[1])
        geo.append(dict(airfoil=name, tc=g["tc"], x_tc=g["x_tc"], camber=g["camber"],
                        n_coords=len(read_coords(P["airfoils"] / f"{name}.dat")[1])))
    pd.DataFrame(geo).to_csv(res_dir / "01_airfoils.csv", index=False)

    jobs = [(n, re) for n in cfg["airfoils"] for re in xs["re_list"]]
    n_exp = int(round((xs["alpha_max"] - xs["alpha_min"]) / xs["alpha_step"])) + 1
    raw, t0, done = {}, time.time(), 0
    print(f"{len(jobs)} XFOIL polars ({len(cfg['airfoils'])} airfoils x {len(xs['re_list'])} Re), "
          f"{xs['workers']} workers", flush=True)
    with ThreadPoolExecutor(xs["workers"]) as ex:
        fut = {ex.submit(cached_polar, xfoil, clean_dir / f"{n}.dat", n, re, xs, P["cache"]): (n, re) for n, re in jobs}
        for f in as_completed(fut):
            n, re = fut[f]
            raw[(n, re)], cached = f.result()
            done += 1
            if done % 20 == 0 or done == len(jobs):
                print(f"  {done}/{len(jobs)}  {time.time()-t0:.0f} s", flush=True)

    cd_max = 1.11 + 0.018 * cfg["viterna"]["aspect_ratio"]
    step = cfg["viterna"]["grid_step"]
    grid = np.arange(-180, 180 + step / 2, step)
    rows = []
    for n in cfg["airfoils"]:
        d = res_dir / "polars" / n
        d.mkdir(parents=True, exist_ok=True)
        for re in xs["re_list"]:
            df = raw[(n, re)]
            df.to_csv(d / f"raw_Re{int(re):06d}.csv", index=False)
            fl = flags(df, n_exp, cfg["reliability"]) if len(df) else dict(n_points=0, conv_rate=0, flag="no points")
            rows.append(dict(airfoil=n, Re=re, **fl))
            if len(df) >= 5:
                cl, cd = bem.viterna_360(df, cd_max, cfg["viterna"]["neg_cl_factor"], grid)
                pd.DataFrame(dict(alpha=grid, CL=cl, CD=cd)).to_csv(d / f"p360_Re{int(re):06d}.csv", index=False)
    s = pd.DataFrame(rows)
    s.to_csv(res_dir / "01_polars_summary.csv", index=False)
    print(f"XFOIL convergence rate (all polars): {s.n_points.sum() / (len(s) * n_exp):.1%}")
    print(f"polars flagged: {(s.flag.fillna('') != '').sum()} of {len(s)}  -> results/01_polars_summary.csv")


if __name__ == "__main__":
    main()
