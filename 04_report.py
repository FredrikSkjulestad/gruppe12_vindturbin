"""Tables, plots, QBlade export and sanity checks.

Reads : results/01_*.csv, results/02_design_summary.csv, results/03_performance_summary.csv,
        results/designs, results/blades, results/performance, results/polars
Writes: results/report/04_results_table.csv          deliverable 1
        results/report/heatmap_Cpmax.png (+ .csv)      deliverable 2
        results/report/top3_*.png                      deliverable 3 (best design of the 3 best airfoils vs GOE 227)
        results/report/winner/                         deliverable 4 (blade table, polars for QBlade, .dat, .bld)
        results/report/sanity_checks.txt               deliverable 5 (also printed)
"""
import shutil

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import bem
from xfoil_runner import read_coords

BASELINE = "goe227__L6.00__A+0.0"        # the earlier Assignment 3/4 design point (GOE 227, lambda 6, alpha_opt)
COLS = ["#2a78d6", "#eb6834", "#1baf7a"]
GRAY = "#8a8984"
plt.rcParams.update({"font.size": 9, "axes.grid": True, "grid.alpha": 0.3,
                     "axes.spines.top": False, "axes.spines.right": False})


def main():
    cfg = bem.load_config()
    rot = cfg["rotor"]
    R = cfg["paths"]["results"]
    out = R / "report"
    out.mkdir(exist_ok=True)
    perf = pd.read_csv(R / "03_performance_summary.csv")

    # ---------------------------------------------------------------- 1. full results table
    t = perf[["rank", "design_id", "airfoil", "lambda_des", "alpha_offset", "alpha_des", "CL", "CD", "CL_CD",
              "Re_conv", "clamped_fraction", "n_clamped_min", "n_clamped_max", "max_clamp_mm", "t_min_mm",
              "Cp_max_TL", "lam_Cp_max_TL", "Cp_max_noTL", "lam_Cp_max_noTL", "Cp_at_lam_des_TL",
              "Cp_at_lam_des_noTL", "Ct_at_lam_des_TL", "Ct_at_Cp_max_TL", "plateau_lo_TL", "plateau_hi_TL", "plateau_width_TL", "constraints_ok",
              "polar_flag_nearest_Re"]]
    t.to_csv(out / "04_results_table.csv", index=False)

    # ---------------------------------------------------------------- 2. heatmap
    # value = the ranking quantity; columns = lambda_des (sweep) or alpha offset (fixed lambda)
    key = cfg["performance"].get("rank_by", "Cp_max_TL")
    hm_col = "lambda_des" if perf.lambda_des.nunique() > 1 else "alpha_offset"
    best = perf[perf.constraints_ok].sort_values(key, ascending=False).drop_duplicates(["airfoil", hm_col])
    hm = best.pivot(index="airfoil", columns=hm_col, values=key)
    hm = hm.loc[hm.max(axis=1).sort_values(ascending=False).index]
    hm.to_csv(out / "heatmap_Cpmax.csv")
    fig, ax = plt.subplots(figsize=(8, 0.34 * len(hm) + 1.6))
    im = ax.imshow(hm.values, cmap="Blues", aspect="auto", vmin=np.nanmin(hm.values), vmax=np.nanmax(hm.values))
    ax.set_xticks(range(hm.shape[1]), [f"{c:.2f}" if hm_col == "lambda_des" else f"{c:+.1f}" for c in hm.columns])
    ax.set_yticks(range(hm.shape[0]), hm.index)
    ax.grid(False)
    mid = np.nanmean([np.nanmin(hm.values), np.nanmax(hm.values)])
    for i in range(hm.shape[0]):
        for j in range(hm.shape[1]):
            v = hm.values[i, j]
            if np.isfinite(v):
                ax.text(j, i, f"{v:.3f}", ha="center", va="center", fontsize=7,
                        color="white" if v > mid else "#0b0b0b")
    if hm_col == "lambda_des":
        ax.set_xlabel("Design tip speed ratio λ_des [-]")
        ax.set_title("$C_{P,max}$ with Prandtl tip loss, realistic (clamped) blade\nbest α_des per cell", loc="left")
    else:
        ax.set_xlabel("α_des − α_opt [deg]")
        ax.set_title(f"$C_P$ at λ = {perf.lambda_des.iloc[0]:g} with Prandtl tip loss, realistic (clamped) blade",
                     loc="left")
    fig.colorbar(im, ax=ax, label="$C_P$ [-]", shrink=0.8)
    fig.tight_layout()
    fig.savefig(out / "heatmap_Cpmax.png", dpi=150)
    plt.close(fig)

    # ---------------------------------------------------------------- 3. top 3 (best design of the 3 best airfoils) vs baseline
    top = perf[perf.constraints_ok].sort_values("rank").drop_duplicates("airfoil").head(3)
    ids = list(top.design_id)
    has_base = (perf.design_id == BASELINE).any()          # GOE 227 is optional (not in the default list)
    base = perf[perf.design_id == BASELINE].iloc[0] if has_base else None
    sets = [(r.design_id, r.airfoil, c, "-") for (_, r), c in zip(top.iterrows(), COLS)]
    if has_base:
        sets.append((BASELINE, "goe227", GRAY, "--"))

    def lab(did):
        a, l, o = did.split("__")
        return f"{a}, λ_des {l[1:]}, Δα {o[1:]}°"

    fig, axs = plt.subplots(len(sets), 1, figsize=(6, 1.3 * len(sets)))
    for ax, (did, foil, col, _) in zip(axs, sets):
        p = read_coords(R / "airfoils_clean" / f"{foil}.dat")[1]
        ax.fill(p[:, 0], p[:, 1], color=col, lw=0)
        ax.set_aspect("equal"); ax.axis("off")
        tc = perf.loc[perf.design_id == did, "tc"].iloc[0]
        ax.set_title(f"{foil}   t/c = {tc*100:.1f} %" + ("  (baseline)" if did == BASELINE else ""), loc="left", fontsize=9)
    fig.tight_layout(); fig.savefig(out / "top3_airfoils.png", dpi=150); plt.close(fig)

    fig, axs = plt.subplots(1, 2, figsize=(11, 4))
    for did, foil, col, ls in sets:
        b = pd.read_csv(R / "blades" / f"{did}.csv")
        d = pd.read_csv(R / "designs" / f"{did}.csv")
        axs[0].plot(b.r / rot["R"], b.chord * 1000, color=col, ls=ls, lw=2, label=lab(did))
        axs[0].plot(d.r_R, d.chord * 1000, color=col, ls=":", lw=1)
        axs[1].plot(b.r / rot["R"], b.theta_deg, color=col, ls=ls, lw=2, label=lab(did))
    for c in (cfg["constraints"]["chord_min"], cfg["constraints"]["chord_max"]):
        axs[0].axhline(c * 1000, color="#52514e", lw=0.8)
    axs[0].set(xlabel="r/R [-]", ylabel="Chord $L_c$ [mm]", title="Chord: realistic blade (solid), ideal BEM (dotted)")
    axs[1].set(xlabel="r/R [-]", ylabel="Twist θ [deg]", title="Twist (kept from BEM)")
    axs[0].legend(frameon=False, fontsize=7)
    fig.tight_layout(); fig.savefig(out / "top3_chord_twist.png", dpi=150); plt.close(fig)

    fig, axs = plt.subplots(1, 2, figsize=(11, 4))
    for did, foil, col, ls in sets:
        c = pd.read_csv(R / "performance" / f"{did}.csv")
        axs[0].plot(c.lam, c.Cp_TL, color=col, ls=ls, lw=2, label=lab(did) + ", tip loss")
        axs[0].plot(c.lam, c.Cp_noTL, color=col, ls=ls, lw=1, alpha=0.6)
        axs[1].plot(c.lam, c.Ct_TL, color=col, ls=ls, lw=2)
        axs[1].plot(c.lam, c.Ct_noTL, color=col, ls=ls, lw=1, alpha=0.6)
    axs[0].axhline(16 / 27, color="#52514e", lw=0.8)
    axs[0].text(2.1, 16 / 27 + 0.005, "Betz 16/27", fontsize=7, color="#52514e")
    axs[0].set(xlabel="Tip speed ratio λ [-]", ylabel="$C_P$ [-]", ylim=(0, 0.62),
               title="$C_P(λ)$: thick = with Prandtl tip loss, thin = without")
    axs[1].set(xlabel="Tip speed ratio λ [-]", ylabel="$C_T$ [-]", title="$C_T(λ)$")
    axs[0].legend(frameon=False, fontsize=7, loc="lower center")
    fig.tight_layout(); fig.savefig(out / "top3_Cp_Ct.png", dpi=150); plt.close(fig)
    top.to_csv(out / "top3_designs.csv", index=False)

    # ---------------------------------------------------------------- 4. winner: blade table + QBlade export
    win = perf[perf.constraints_ok].sort_values("rank").iloc[0]
    wd = out / "winner"
    (wd / "Polars").mkdir(parents=True, exist_ok=True)       # files are overwritten (no rmtree: OneDrive may lock folders)
    b = pd.read_csv(R / "blades" / f"{win.design_id}.csv")
    wt = pd.DataFrame({"r_m": b.r, "r_minus_rhub_m": b.r_minus_rhub, "chord_m": b.chord, "twist_deg": b.theta_deg,
                       "airfoil": np.where(b.foil == "cyl", "circular (48 mm cylinder)", win.airfoil),
                       "chord_bem_m": b.chord_bem, "clamped": b.clamped, "t_max_mm": b.t_max_mm})
    wt.to_csv(wd / "winning_blade.csv", index=False)
    shutil.copy(R / "airfoils_clean" / f"{win.airfoil}.dat", wd / f"{win.airfoil}.dat")
    pol = bem.load_polarset(win.airfoil, cfg)
    for re in pol.re:
        raw = pol.raw[re]
        write_xfoil_format(wd / "Polars" / f"{win.airfoil}_Re{re/1e6:.3f}_N{cfg['xfoil']['ncrit']}.txt", win.airfoil, re, raw, cfg)
        i = list(pol.re).index(re)
        write_plr(wd / "Polars" / f"{win.airfoil}_Re{re/1e6:.3f}_N{cfg['xfoil']['ncrit']}_360_V.plr",
                  win.airfoil, re, pol.alpha, pol.CL[i], pol.CD[i], perf.loc[perf.design_id == win.design_id, "tc"].iloc[0])
    grid = pol.alpha
    write_plr(wd / "Polars" / "circular_360.plr", "circular", 1e5, grid,
              np.full_like(grid, cfg["realistic"]["cyl_CL"]), np.full_like(grid, cfg["realistic"]["cyl_CD"]), 1.0)
    re_pick = pol.re[np.argmin(np.abs(pol.re - win.Re_conv))]
    write_bld(wd / f"{win.design_id}.bld", b, win.airfoil,
              f"Polars/{win.airfoil}_Re{re_pick/1e6:.3f}_N{cfg['xfoil']['ncrit']}_360_V.plr", rot["Z"])
    shutil.copy(R / "performance" / f"{win.design_id}.csv", wd / "winner_Cp_Ct.csv")
    write_qblade_folder(wd / "qblade", win, b, pol, re_pick, cfg,
                        perf.loc[perf.design_id == win.design_id, "tc"].iloc[0], R)

    # ---------------------------------------------------------------- 4b. comparison with the NeuralFoil prescreen (optional)
    nf_file = cfg["paths"]["airfoils"].parent / "validation" / "neuralfoil_lambda54.csv"
    if nf_file.exists() and hm_col == "alpha_offset":
        nf = pd.read_csv(nf_file)
        bx = perf[perf.constraints_ok].sort_values("rank").drop_duplicates("airfoil")
        cmp = bx[["airfoil", "rank", "alpha_offset", "alpha_des", "CL", "CL_CD", "Re_conv", "Cp_at_lam_des_TL",
                  "Ct_at_lam_des_TL", "Cp_max_TL", "lam_Cp_max_TL", "t_min_mm", "n_clamped_min", "n_clamped_max"]]
        cmp = cmp.add_suffix("_xfoil").rename(columns={"airfoil_xfoil": "airfoil"})
        cmp = nf.add_suffix("_nf").rename(columns={"airfoil_nf": "airfoil"}).merge(cmp, on="airfoil", how="left")
        cmp["dCp_xfoil_minus_nf"] = cmp.Cp_at_lam_des_TL_xfoil - cmp.Cp_lam54_nf
        cmp.to_csv(out / "xfoil_vs_neuralfoil.csv", index=False)

    # ---------------------------------------------------------------- 5. sanity checks
    ps = pd.read_csv(R / "01_polars_summary.csv")
    ds = pd.read_csv(R / "02_design_summary.csv")
    n_exp = int(round((cfg["xfoil"]["alpha_max"] - cfg["xfoil"]["alpha_min"]) / cfg["xfoil"]["alpha_step"])) + 1
    w = perf[perf.design_id == win.design_id].iloc[0]
    lines = [
        "SANITY CHECKS",
        f"XFOIL convergence rate          : {ps.n_points.sum() / (len(ps) * n_exp):.1%} over {len(ps)} polars "
        f"({(ps.flag.fillna('') != '').sum()} flagged, see 01_polars_summary.csv)",
        f"Cp below Betz (16/27) everywhere: {bool(perf.below_betz.all())}  (max Cp_max without tip loss "
        f"{perf.Cp_max_noTL.max():.3f})",
        f"Design a outboard (r/R > 0.3)   : {ds.a_outboard_min.min():.3f} .. {ds.a_outboard_max.max():.3f}  (expect about 1/3)",
        f"Design CT (Assignment 3 method) : {ds.Ct_design.min():.3f} .. {ds.Ct_design.max():.3f}  (expect about 8/9)",
        f"BEM residual > 1e-4             : {(perf.bem_residual_max > 1e-4).sum()} of {len(perf)} designs",
        "",
        f"WINNER {win.design_id}",
        f"  Cp at λ_des {w.lambda_des:g}: {w.Cp_at_lam_des_TL:.4f} with tip loss (CT {w.Ct_at_lam_des_TL:.3f}), "
        f"{w.Cp_at_lam_des_noTL:.4f} without",
        f"  Cp_max {w.Cp_max_TL:.4f} at λ {w.lam_Cp_max_TL:.1f} with tip loss; {w.Cp_max_noTL:.4f} at λ {w.lam_Cp_max_noTL:.1f} without",
        f"  α_opt {w.alpha_des - w.alpha_offset:.2f}°, α_des {w.alpha_des:.2f}°, CL {w.CL:.3f}, CL/CD {w.CL_CD:.1f}, Re_des {w.Re_conv:,.0f}",
        f"  local Re at the operating point : {w.Re_min_op:,.0f} .. {w.Re_max_op:,.0f} "
        f"(polar grid {pol.re.min():,.0f} .. {pol.re.max():,.0f}; {w.frac_panels_outside_Re_grid:.0%} of panels outside)",
        f"  rotational / axial term in W    : {w.rot_over_axial_07_op:.1f} at r/R = 0.7, {w.rot_over_axial_min_op:.1f} at the innermost airfoil panel",
        f"  clamped elements                : {int(w.n_clamped)} of {int(w.n_elements)} "
        f"({int(w.n_clamped_min)} raised to 40 mm, {int(w.n_clamped_max)} cut to 100 mm), max change {w.max_clamp_mm:.1f} mm",
        f"  thinnest section                : {w.t_min_mm:.2f} mm (limit 5 mm)",
        "",
    ]
    if has_base:
        lines += [f"BASELINE {BASELINE}: Cp_max {base.Cp_max_TL:.3f} at λ {base.lam_Cp_max_TL:.1f} with tip loss",
                  f"Gain of winner over baseline    : {w.Cp_max_TL - base.Cp_max_TL:+.3f} ({(w.Cp_max_TL / base.Cp_max_TL - 1):+.1%})"]
    lines.append("Earlier GOE 227 blade in QBlade (Assignment 4): Cp_max 0.427 at λ 5.6 with tip loss")
    txt = "\n".join(lines)
    (out / "sanity_checks.txt").write_text(txt, encoding="utf-8")
    print(txt)
    print("\nTop 10:")
    print(perf.head(10)[["rank", "design_id", "Cp_at_lam_des_TL", "Cp_max_TL", "lam_Cp_max_TL", "Cp_max_noTL",
                         "CL_CD", "clamped_fraction", "t_min_mm"]].to_string(index=False))


# ------------------------------------------------------------------ QBlade / XFOIL exports
def write_xfoil_format(path, name, re, df, cfg):
    """Plain XFOIL polar file (same layout as QBlade's 'export polar'); QBlade: Import Polar -> XFoil format."""
    with open(path, "w", newline="\n", encoding="utf-8") as f:
        f.write(f"\n       XFOIL         Version 6.99\n\n Calculated polar for: {name}\n\n"
                f" 1 1 Reynolds number fixed          Mach number fixed\n\n"
                f" xtrf =   1.000 (top)        1.000 (bottom)\n"
                f" Mach =   0.000     Re = {re/1e6:9.3f} e 6     Ncrit = {cfg['xfoil']['ncrit']:7.3f}\n\n"
                f"  alpha    CL        CD       CDp       CM     Top_Xtr  Bot_Xtr\n"
                f" ------ -------- --------- --------- -------- -------- --------\n")
        for _, r in df.iterrows():
            f.write(f" {r.alpha:6.3f} {r.CL:8.4f} {r.CD:9.5f} {r.CDp:9.5f} {r.CM:8.4f}   1.0000   1.0000\n")


def write_plr(path, name, re, alpha, cl, cd, tc, foilfile=None):
    """QBlade 360 deg polar file (layout copied from the QBlade CE 2.0.9 file in validation/), not decomposed."""
    with open(path, "w", newline="\n", encoding="utf-8") as f:
        f.write("----------------------------------------QBlade Multi RE Polar File--------------------------------------------------\n"
                "Generated with : wind_blade (TEP4175)\nArchive Format: 310043\n\n"
                "----------------------------------------Object Names----------------------------------------------------------------\n"
                f"{name + f'_Re{re/1e6:.3f}_360_V':<51s}POLARNAME          - the polar name\n"
                f"{(foilfile or name):<51s}FOILNAME           - the airfoil name to which the polar(s) belong OR path to airfoil file\n\n"
                "----------------------------------------Parameters------------------------------------------------------------------\n"
                f"{tc*100:<51.1f}THICKNESS          - the thickness of the airfoil in % of chord\n"
                f"{'false':<51s}ISDECOMPOSED       - is the polar decomposed [bool]\n"
                f"REYNOLDS            {re:.4E}          - the list of Reynolds numbers for the imported polars\n\n"
                "----------------------------------------Polar Data------------------------------------------------------------------\n"
                f"{'AOA':<20s}{'CL':<20s}{'CD':<20s}{'CM':<20s}\n")
        for a, l, d in zip(alpha, cl, cd):
            f.write(f"{a:<20.6f}{l:<20.6f}{d:<20.6f}{0.0:<20.6f}\n")


def write_qblade_folder(qd, win, blade, pol, re_pick, cfg, tc, R):
    """Self-contained folder laid out like QBlade's own export (see Assignment3_Rotor.bld):
         <design>.bld, Polars/*.plr (FOILNAME -> ../Airfoils/*.afl), Airfoils/*.afl
    In QBlade: HAWT Blade Design -> import the .bld; the polars and airfoils are loaded with it."""
    (qd / "Polars").mkdir(parents=True, exist_ok=True)
    (qd / "Airfoils").mkdir(exist_ok=True)
    foil = win.airfoil
    shutil.copy(R / "airfoils_clean" / f"{foil}.dat", qd / "Airfoils" / f"{foil}.afl")
    th = np.linspace(0, 2 * np.pi, 121)                          # circle, unit chord, TE -> upper -> LE -> lower
    with open(qd / "Airfoils" / "circular.afl", "w", newline="\n", encoding="utf-8") as f:
        f.write("circular\n")
        for t in th:
            f.write(f"{0.5 + 0.5 * np.cos(t):10.6f} {0.5 * np.sin(t):10.6f}\n")
    i = list(pol.re).index(re_pick)
    pname = f"{foil}_Re{re_pick/1e6:.3f}_N{cfg['xfoil']['ncrit']}_360_V.plr"
    write_plr(qd / "Polars" / pname, foil, re_pick, pol.alpha, pol.CL[i], pol.CD[i], tc, f"../Airfoils/{foil}.afl")
    write_plr(qd / "Polars" / "circular_360.plr", "circular", re_pick, pol.alpha,
              np.full_like(pol.alpha, cfg["realistic"]["cyl_CL"]), np.full_like(pol.alpha, cfg["realistic"]["cyl_CD"]),
              100.0, "../Airfoils/circular.afl")
    write_bld(qd / f"{win.design_id}.bld", blade, foil, f"Polars/{pname}", cfg["rotor"]["Z"])


def write_bld(path, blade, foil, polar_file, Z):
    """QBlade blade definition (layout copied from Assignment3_Rotor.bld)."""
    with open(path, "w", newline="\n", encoding="utf-8") as f:
        f.write("----------------------------------------QBlade Blade Definition File------------------------------------------------\n"
                "Generated with : wind_blade (TEP4175)\nArchive Format: 310043\n\n"
                "----------------------------------------Object Name-----------------------------------------------------------------\n"
                f"{path.stem:<51s}OBJECTNAME         - the name of the blade object\n\n"
                "----------------------------------------Parameters------------------------------------------------------------------\n"
                f"{'HAWT':<51s}ROTORTYPE          - the rotor type\n"
                f"{'false':<51s}INVERTEDFOILS      - invert the airfoils? (only VAWT) [bool]\n"
                f"{Z:<51d}NUMBLADES          - number of blades\n\n"
                "----------------------------------------Blade Data------------------------------------------------------------------\n"
                "POS_[m]             CHORD_[m]           TWIST_[deg]         OFFSET_Y_[m]        OFFSET_X_[m]        "
                "P_AXIS_Y_[-]        P_AXIS_X_[-]        POLAR_FILE          \n")
        for _, s in blade.iterrows():
            pf = "Polars/circular_360.plr" if s.foil == "cyl" else polar_file
            f.write(f"{s.r:<20.5f}{s.chord:<20.5f}{s.theta_deg:<20.2f}{0:<20.5f}{0:<20.5f}{0.5:<20.5f}{0:<20.5f}{pf}\n")


if __name__ == "__main__":
    main()
