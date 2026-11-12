"""Step 3 (replaces Assignment 3): BEM blade design for every airfoil, lambda_des and alpha_des.

For each design: Step 1 + 2 (Re iteration at r/R = 0.7, tol 30 000) and Step 3 (chord, twist,
a, a', phi at all N elements) exactly as in the Assignment 3 flow charts; no tip loss in the design
(as in Assignment 3). alpha_des = alpha_opt + offset. With design.alpha_offset_min/max set in config.yaml,
every offset in that range is designed (lambda 5.4 study: +2 .. -4 deg in 0.5 deg steps). Without them:
offset = 0, -0.5, -1, ... until CL/CD at alpha_des has dropped more than 10 % below its maximum.

Reads : config.yaml, results/polars/*/raw_Re*.csv, results/01_polars_summary.csv
Writes: results/designs/<design_id>.csv   element table (r/R, Lc/R, theta, a, a', phi, Re, Z dT', Z dM')
        results/02_design_summary.csv     one row per design
"""
import numpy as np
import pandas as pd

import bem


def main():
    cfg = bem.load_config()
    res_dir = cfg["paths"]["results"]
    out = res_dir / "designs"
    out.mkdir(parents=True, exist_ok=True)
    flags = pd.read_csv(res_dir / "01_polars_summary.csv")
    geo = pd.read_csv(res_dir / "01_airfoils.csv").set_index("airfoil")
    dcfg = cfg["design"]
    rows = []
    for name in cfg["airfoils"]:
        pol = bem.load_polarset(name, cfg)
        fixed = dcfg.get("alpha_offset_min") is not None          # fixed offset range (lambda 5.4 study)
        if fixed:
            st = dcfg["alpha_offsets_step"]
            offsets = np.round(np.arange(dcfg["alpha_offset_max"], dcfg["alpha_offset_min"] - st / 2, -st), 3)
        for lam in dcfg["lambdas"]:
            k = 0
            while True:
                if fixed:
                    if k >= len(offsets):
                        break
                    off = float(offsets[k]) + 0.0
                else:
                    off = -k * dcfg["alpha_offsets_step"]
                conv = bem.converge_re(pol, lam, off, cfg)
                if conv is None:
                    if fixed:                                    # e.g. alpha_des beyond the converged polar
                        k += 1
                        continue
                    break
                ratio = conv["LD"] / conv["LDmax"]
                if not fixed and ratio < 1 - dcfg["ld_drop"] - 1e-9:
                    break
                blade = bem.design_blade(lam, conv, cfg)
                perf = bem.design_point_perf(blade, lam, cfg)
                did = f"{name}__L{lam:.2f}__A{off:+.1f}"
                blade.insert(0, "design_id", did)
                blade.to_csv(out / f"{did}.csv", index=False)
                fl = flags[flags.airfoil == name]
                near = fl.iloc[int(np.argmin(np.abs(fl.Re - conv["re_conv"])))]
                rows.append(dict(design_id=did, airfoil=name, lambda_des=lam, alpha_offset=off,
                                 alpha_opt=conv["alpha_opt"], alpha_des=conv["alpha_des"],
                                 CL=conv["CL"], CD=conv["CD"], CL_CD=conv["LD"], LD_ratio=ratio,
                                 Re_first=conv["re_first"], Re_conv=conv["re_conv"], n_iter=conv["n_iter"],
                                 tc=geo.loc[name, "tc"],
                                 chord_tip_bem_mm=blade.chord.iloc[-1] * 1000,
                                 chord_max_bem_mm=blade.chord.max() * 1000,
                                 n_below_min=int((blade.chord < cfg["constraints"]["chord_min"]).sum()),
                                 a_outboard_min=blade.a[blade.r_R > 0.3].min(),
                                 a_outboard_max=blade.a[blade.r_R > 0.3].max(),
                                 polar_flag_nearest_Re=near.flag if isinstance(near.flag, str) else "",
                                 **perf))
                k += 1
        print(f"{name:14s} designs: {sum(r['airfoil'] == name for r in rows)}", flush=True)
    pd.DataFrame(rows).to_csv(res_dir / "02_design_summary.csv", index=False)
    print(f"{len(rows)} designs -> results/02_design_summary.csv")


if __name__ == "__main__":
    main()
