"""Step 4 (replaces Assignment 4): realistic blade, constraints, off-design BEM and ranking.

For every design from Step 3:
  - realistic blade as in Assignment 4 (root cut r < r_hub, 48 mm cylinder at r_hub with theta = 0,
    tip section at r = R copying the last element); chord clamped to 40..100 mm, twist kept from BEM
  - t_max = (t/c) c >= 5 mm checked at every section
  - steady BEM for lambda = 2..10 with Prandtl tip loss ON and OFF, Re-dependent polars
    (local Re from local W and chord at every panel and every lambda)
Ranking (only designs meeting all constraints): performance.rank_by in config.yaml (Cp at lambda_des with
tip loss for the fixed-lambda study, Cp_max with tip loss for the lambda sweep), then CL/CD at alpha_des,
plateau width, clamped fraction.

Reads : config.yaml, results/02_design_summary.csv, results/designs/*.csv, results/polars/*
Writes: results/blades/<design_id>.csv        realistic blade stations (+ clamping record)
        results/performance/<design_id>.csv   Cp, CT, P, Q, T vs lambda, tip loss on/off
        results/03_performance_summary.csv    all designs, ranked
"""
import time

import numpy as np
import pandas as pd

import bem

BETZ = 16 / 27


def main():
    cfg = bem.load_config()
    rot, pf = cfg["rotor"], cfg["performance"]
    res_dir = cfg["paths"]["results"]
    (res_dir / "blades").mkdir(exist_ok=True)
    (res_dir / "performance").mkdir(exist_ok=True)
    summ = pd.read_csv(res_dir / "02_design_summary.csv")
    lams = np.round(np.arange(pf["lambda_min"], pf["lambda_max"] + 1e-9, pf["lambda_step"]), 3)
    rows, t0 = [], time.time()
    for name, grp in summ.groupby("airfoil", sort=False):
        pol = bem.load_polarset(name, cfg)
        re_lo, re_hi = pol.re.min(), pol.re.max()
        for _, d in grp.iterrows():
            design = pd.read_csv(res_dir / "designs" / f"{d.design_id}.csv")
            blade, info = bem.realistic_blade(design, d.tc, cfg)
            blade.insert(0, "design_id", d.design_id)
            blade.to_csv(res_dir / "blades" / f"{d.design_id}.csv", index=False)
            pan = bem.panels(blade, pf["n_panels"], rot["R"], rot["r_hub"])
            out = {tl: bem.bem_sweep(pan, pol, lams, cfg, tl) for tl in (True, False)}
            curve = pd.DataFrame(dict(lam=lams,
                                      Cp_TL=out[True]["Cp"], Ct_TL=out[True]["Ct"], P_TL=out[True]["P"],
                                      Q_TL=out[True]["Q"], T_TL=out[True]["T"],
                                      Cp_noTL=out[False]["Cp"], Ct_noTL=out[False]["Ct"]))
            curve.to_csv(res_dir / "performance" / f"{d.design_id}.csv", index=False)
            s_tl = bem.summarise(out[True], pf["plateau_frac"])
            s_no = bem.summarise(out[False], pf["plateau_frac"])
            i_des = int(np.argmin(np.abs(lams - d.lambda_des)))
            # operating point for the sanity numbers: lambda_des when lambda is fixed, else lambda of Cp_max
            i_op = i_des if pf.get("rank_by") == "Cp_at_lam_des_TL" else int(np.argmax(out[True]["Cp"]))
            foil = pan["w"] > 0.999                                        # airfoil panels only
            Re_op = out[True]["Re"][i_op][foil]
            rows.append(dict(
                design_id=d.design_id, airfoil=name, lambda_des=d.lambda_des, alpha_offset=d.alpha_offset,
                alpha_des=d.alpha_des, CL=d.CL, CD=d.CD, CL_CD=d.CL_CD, Re_conv=d.Re_conv, tc=d.tc,
                Cp_design_A3=d.Cp_design,
                **info,
                Cp_max_TL=s_tl["Cp_max"], lam_Cp_max_TL=s_tl["lam_at_Cp_max"], Ct_at_Cp_max_TL=s_tl["Ct_at_Cp_max"],
                plateau_lo_TL=s_tl["plateau_lo"], plateau_hi_TL=s_tl["plateau_hi"], plateau_width_TL=s_tl["plateau_width"],
                Cp_at_lam_des_TL=float(out[True]["Cp"][i_des]), Ct_at_lam_des_TL=float(out[True]["Ct"][i_des]),
                lam_grid_at_des=float(lams[i_des]),
                Cp_max_noTL=s_no["Cp_max"], lam_Cp_max_noTL=s_no["lam_at_Cp_max"],
                Cp_at_lam_des_noTL=float(out[False]["Cp"][i_des]),
                # sanity numbers at the operating point (see i_op)
                Re_min_op=float(Re_op.min()), Re_max_op=float(Re_op.max()),
                frac_panels_outside_Re_grid=float(((Re_op < re_lo) | (Re_op > re_hi)).mean()),
                rot_over_axial_min_op=float(out[True]["rot_ratio"][i_op][foil].min()),   # innermost airfoil panel
                rot_over_axial_07_op=float(np.interp(0.7 * rot["R"], pan["r"], out[True]["rot_ratio"][i_op])),
                alpha_tip_op=float(out[True]["alpha"][i_op][-1]),
                a_mid_op=float(np.interp(0.7 * rot["R"], pan["r"], out[True]["a"][i_op])),
                bem_residual_max=float(max(out[True]["residual"], out[False]["residual"])),
                below_betz=bool(s_no["Cp_max"] < BETZ and s_tl["Cp_max"] < BETZ),
                polar_flag_nearest_Re=d.polar_flag_nearest_Re if isinstance(d.polar_flag_nearest_Re, str) else ""))
        print(f"{name:14s} done  ({time.time()-t0:.0f} s)", flush=True)
    df = pd.DataFrame(rows)
    key = pf.get("rank_by", "Cp_max_TL")                                  # config.yaml -> performance.rank_by
    ok = df[df.constraints_ok].sort_values(
        [key, "CL_CD", "plateau_width_TL", "clamped_fraction"],
        ascending=[False, False, False, True])
    df["rank"] = np.nan
    df.loc[ok.index, "rank"] = np.arange(1, len(ok) + 1)
    df = df.sort_values(["rank", key], ascending=[True, False])
    df.to_csv(res_dir / "03_performance_summary.csv", index=False)
    print(f"{len(df)} designs, {len(ok)} meet all constraints -> results/03_performance_summary.csv")
    print(f"ranked by {key}")
    print(df.head(10)[["rank", "design_id", "Cp_at_lam_des_TL", "Cp_max_TL", "lam_Cp_max_TL", "Cp_max_noTL",
                       "CL_CD", "clamped_fraction", "t_min_mm"]].to_string(index=False))


if __name__ == "__main__":
    main()
