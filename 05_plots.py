"""Plots of the best designs, the same kinds of graphs as in Assignments 1, 3 and 4.

By default the best design of each of the top 4 airfoils (from 03_performance_summary.csv).
Change N_TOP, or list design_ids in DESIGNS to plot something else.

Reads : results/03_performance_summary.csv, results/polars, results/designs, results/blades, results/performance
Writes: results/plots/A1_polars.png            CL, CD, CL/CD vs alpha at the design Re (A1 Fig. 1-3)
        results/plots/A1_reynolds_effect.png   CL/CD vs alpha for every Re, one panel per airfoil
        results/plots/A1_polars_360.png        Viterna 360 deg CL and CD (A1 section 2.8)
        results/plots/A3_blade_design.png      Lc/R, theta, a, a', Re, Z dT', Z dM' along the blade (A3 s.5.2-5.3)
        results/plots/A4_performance.png       Cp and CT vs lambda with/without tip loss, torque vs rpm (A4 s.7)
        results/plots/A4_blade_operating.png   realistic chord and twist + alpha, a, Re along the blade at Cp_max (A4 s.6)
"""
import sys

import numpy as np
import pandas as pd
import matplotlib

# The figures are saved AND shown in windows at the end of the run.
# Run with --no-show to only save them (e.g. on a machine without a screen).
SHOW = "--no-show" not in sys.argv
if not SHOW:
    matplotlib.use("Agg")
import matplotlib.pyplot as plt

import bem

N_TOP = 5
DESIGNS = []            # e.g. ["e68__L6.50__A-1.0", "mh114__L6.00__A-2.0"]; empty = top N_TOP airfoils
COLS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#4a3aa7"]     # fixed order, one per design
INK2 = "#52514e"
plt.rcParams.update({"font.size": 9, "axes.grid": True, "grid.alpha": 0.3, "grid.linewidth": 0.6,
                     "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False,
                     "savefig.dpi": 150, "figure.facecolor": "white"})


def finish(fig, path):
    """Save the figure; keep it open for the final plt.show() unless --no-show."""
    fig.savefig(path)
    if not SHOW:
        plt.close(fig)


def pick(perf):
    if DESIGNS:
        return perf.set_index("design_id").loc[DESIGNS].reset_index()
    ok = perf[perf.constraints_ok].sort_values("rank")
    return ok.drop_duplicates("airfoil").head(N_TOP).reset_index(drop=True)


def label(r):
    return f"{r.airfoil} (λ_des {r.lambda_des:g}, α_des {r.alpha_des:.1f}°)"


def lam_op(r):
    """Operating point: lambda_des when lambda is fixed (rank_by Cp_at_lam_des_TL), else lambda of Cp_max."""
    return r.lambda_des if bem.load_config()["performance"].get("rank_by") == "Cp_at_lam_des_TL" else r.lam_Cp_max_TL


def nearest(pol, re):
    return pol.re[int(np.argmin(np.abs(pol.re - re)))]


def main():
    cfg = bem.load_config()
    rot, pf = cfg["rotor"], cfg["performance"]
    R = cfg["paths"]["results"]
    out = R / "plots"
    out.mkdir(exist_ok=True)
    perf = pd.read_csv(R / "03_performance_summary.csv")
    top = pick(perf)
    pols = {r.airfoil: bem.load_polarset(r.airfoil, cfg) for _, r in top.iterrows()}
    print("Plotting:", ", ".join(top.design_id))

    # ============================================================ Assignment 1: polars at the design Re
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.3))
    for (_, r), c in zip(top.iterrows(), COLS):
        pol = pols[r.airfoil]
        re = nearest(pol, r.Re_conv)
        p = pol.raw[re]
        lab = f"{r.airfoil}, Re {re/1e3:.0f}k"
        ax[0].plot(p.alpha, p.CL, color=c, lw=2, label=lab)
        ax[1].plot(p.alpha, p.CD, color=c, lw=2)
        ax[2].plot(p.alpha, p.CL / p.CD, color=c, lw=2)
        ax[2].plot(r.alpha_des, r.CL_CD, "o", color=c, ms=7, mec="white", mew=1.5)
        ax[0].plot(r.alpha_des, r.CL, "o", color=c, ms=7, mec="white", mew=1.5)
    ax[0].set(xlabel="Angle of attack α [deg]", ylabel="$C_L$ [-]", title="Lift coefficient")
    ax[1].set(xlabel="Angle of attack α [deg]", ylabel="$C_D$ [-]", title="Drag coefficient")
    ax[2].set(xlabel="Angle of attack α [deg]", ylabel="$C_L/C_D$ [-]", title="Aerodynamic efficiency")
    ax[0].legend(fontsize=8)
    ax[2].text(0.02, 0.02, "dots: design point α_des (values at the converged design Re)", transform=ax[2].transAxes, fontsize=8, color=INK2)
    fig.suptitle(f"XFOIL polars at the polar Re closest to each design's converged Re (Ncrit {cfg['xfoil']['ncrit']}), "
                 "before Viterna extrapolation", x=0.01, ha="left")
    fig.tight_layout(); finish(fig, out / "A1_polars.png")

    # ============================================================ Assignment 1: Reynolds effect
    fig, axs = plt.subplots(1, len(top), figsize=(4.2 * len(top), 4), sharey=True)
    axs = np.atleast_1d(axs)
    cmap = plt.get_cmap("Blues")
    for ax, (_, r) in zip(axs, top.iterrows()):
        pol = pols[r.airfoil]
        for k, re in enumerate(pol.re):
            p = pol.raw[re]
            ax.plot(p.alpha, p.CL / p.CD, color=cmap(0.3 + 0.7 * k / max(len(pol.re) - 1, 1)), lw=1.6,
                    label=f"{re/1e3:.0f}k")
        ax.set(title=r.airfoil, xlabel="Angle of attack α [deg]")
    axs[0].set_ylabel("$C_L/C_D$ [-]")
    axs[-1].legend(title="Re", fontsize=7, ncol=2)
    fig.suptitle("Effect of Reynolds number on $C_L/C_D$ (light = low Re, dark = high Re)", x=0.01, ha="left")
    fig.tight_layout(); finish(fig, out / "A1_reynolds_effect.png")

    # ============================================================ Assignment 1: 360 deg polars
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.3))
    for (_, r), c in zip(top.iterrows(), COLS):
        pol = pols[r.airfoil]
        re = nearest(pol, r.Re_conv)
        i = list(pol.re).index(re)
        ax[0].plot(pol.alpha, pol.CL[i], color=c, lw=1.8, label=f"{r.airfoil}, Re {re/1e3:.0f}k")
        ax[1].plot(pol.alpha, pol.CD[i], color=c, lw=1.8)
    a0, a1 = cfg["xfoil"]["alpha_min"], cfg["xfoil"]["alpha_max"]
    for a in ax:
        a.axvspan(a0, a1, color="#ecebe8", zorder=0)
        a.set(xlim=(-180, 180), xticks=range(-180, 181, 45), xlabel="Angle of attack α [deg]")
    ax[0].set(ylabel="$C_L$ [-]", title="Lift, 360° (Viterna)")
    ax[1].set(ylabel="$C_D$ [-]", title="Drag, 360° (Viterna)")
    ax[0].legend(fontsize=8)
    ax[0].text(0.5, 0.02, "shaded: XFOIL data range", transform=ax[0].transAxes, ha="center", fontsize=8, color=INK2)
    fig.tight_layout(); finish(fig, out / "A1_polars_360.png")

    # ============================================================ Assignment 3: preliminary blade design
    fig, ax = plt.subplots(2, 3, figsize=(15, 8))
    ax = ax.ravel()
    for (_, r), c in zip(top.iterrows(), COLS):
        d = pd.read_csv(R / "designs" / f"{r.design_id}.csv")
        kw = dict(color=c, lw=2, marker="o", ms=3.5)
        ax[0].plot(d.r_R, d.Lc_R, label=label(r), **kw)
        ax[1].plot(d.r_R, d.theta_deg, **kw)
        ax[2].plot(d.r_R, d.a, **kw)
        ax[2].plot(d.r_R, d.a_prime, color=c, lw=1.2, ls="--", marker="s", ms=3)
        ax[3].plot(d.r_R, d.Re / 1e3, **kw)
        ax[4].plot(d.r_R, d.ZdT, **kw)
        ax[5].plot(d.r_R, d.ZdM, **kw)
    cmin = cfg["constraints"]["chord_min"] / rot["R"]
    ax[0].axhline(cmin, color=INK2, lw=0.8)
    ax[0].text(0.02, cmin * 1.04, "40 mm", fontsize=8, color=INK2)
    ax[0].set(ylabel="$L_c/R$ [-]", title="Chord (ideal BEM)")
    ax[1].set(ylabel="Twist θ [deg]", title="Twist")
    ax[2].axhline(1 / 3, color=INK2, lw=0.8)
    ax[2].set(ylabel="a (solid), a' (dashed) [-]", title="Induction factors (a' at the root element is off scale)",
              ylim=(0, 0.45))
    ax[3].set(ylabel="Local Re [×10³]", title="Reynolds number along the blade")
    ax[4].set(ylabel="$Z\\,dT'$ [N]", title="Thrust per element")
    ax[5].set(ylabel="$Z\\,dM'$ [N]", title="Tangential force per element")
    for a in ax:
        a.set_xlabel("r/R [-]")
    ax[0].legend(fontsize=7.5)
    fig.suptitle("Preliminary blade design (Assignment 3 method, N = 15, no tip loss)", x=0.01, ha="left")
    fig.tight_layout(); finish(fig, out / "A3_blade_design.png")

    # ============================================================ Assignment 4: performance curves
    fig, ax = plt.subplots(1, 3, figsize=(16, 4.5))
    for (_, r), c in zip(top.iterrows(), COLS):
        cu = pd.read_csv(R / "performance" / f"{r.design_id}.csv")
        ax[0].plot(cu.lam, cu.Cp_TL, color=c, lw=2, label=label(r))
        ax[0].plot(cu.lam, cu.Cp_noTL, color=c, lw=1.2, ls="--")
        ax[0].plot(r.lam_Cp_max_TL, r.Cp_max_TL, "o", color=c, ms=7, mec="white", mew=1.5)
        ax[0].plot(r.lambda_des, r.Cp_at_lam_des_TL, "D", color=c, ms=5, mec="white", mew=1)
        ax[1].plot(cu.lam, cu.Ct_TL, color=c, lw=2)
        ax[1].plot(cu.lam, cu.Ct_noTL, color=c, lw=1.2, ls="--")
        rpm = cu.lam * rot["V1"] / rot["R"] * 60 / (2 * np.pi)
        ax[2].plot(rpm, cu.Q_TL, color=c, lw=2)
        i = int(np.argmax(cu.Cp_TL))
        ax[2].plot(rpm[i], cu.Q_TL[i], "o", color=c, ms=7, mec="white", mew=1.5)
    ax[0].axhline(16 / 27, color=INK2, lw=0.8)
    ax[0].text(2.1, 16 / 27 + 0.006, "Betz 16/27", fontsize=8, color=INK2)
    ax[0].set(xlabel="Tip speed ratio λ [-]", ylabel="$C_P$ [-]", ylim=(0, 0.62), title="Power coefficient")
    ax[1].set(xlabel="Tip speed ratio λ [-]", ylabel="$C_T$ [-]", title="Thrust coefficient")
    ax[2].set(xlabel="Rotational speed [rpm]", ylabel="Torque [N m]", title="Torque with tip loss, $V_1$ = 12 m/s")
    ax[0].legend(fontsize=7.5, loc="lower center")
    ax[1].text(0.02, 0.92, "solid: Prandtl tip loss\ndashed: no tip loss", transform=ax[1].transAxes, fontsize=8,
               color=INK2, va="top")
    ax[0].text(0.02, 0.92, "dots: $C_{P,max}$ with tip loss\ndiamonds: $C_P$ at λ_des", transform=ax[0].transAxes,
               fontsize=8, color=INK2, va="top")
    fig.suptitle("Realistic blade performance (Assignment 4: hub cylinder, chord 40 to 100 mm)", x=0.01, ha="left")
    fig.tight_layout(); finish(fig, out / "A4_performance.png")

    # ============================================================ Assignment 4: blade and operating point
    fig, ax = plt.subplots(2, 3, figsize=(15, 8))
    ax = ax.ravel()
    for (_, r), c in zip(top.iterrows(), COLS):
        b = pd.read_csv(R / "blades" / f"{r.design_id}.csv")
        d = pd.read_csv(R / "designs" / f"{r.design_id}.csv")
        ax[0].plot(b.r / rot["R"], b.chord * 1000, color=c, lw=2, marker="o", ms=3.5, label=label(r))
        ax[0].plot(d.r_R, d.chord * 1000, color=c, lw=1, ls=":")
        ax[1].plot(b.r / rot["R"], b.theta_deg, color=c, lw=2, marker="o", ms=3.5)
        af = b[b.foil != "cyl"]                     # cylinder (48 mm) left out so the scale stays readable
        ax[2].plot(af.r / rot["R"], af.t_max_mm, color=c, lw=2, marker="o", ms=3.5)
        pan = bem.panels(b, pf["n_panels"], rot["R"], rot["r_hub"])
        res = bem.bem_sweep(pan, pols[r.airfoil], np.array([lam_op(r)]), cfg, True)
        foil = pan["w"] > 0.999
        x = pan["r"] / rot["R"]
        ax[3].plot(x[foil], res["alpha"][0][foil], color=c, lw=2)
        ax[3].axhline(r.alpha_des, color=c, lw=0.8, ls=":")
        ax[4].plot(x, res["a"][0], color=c, lw=2)
        ax[5].plot(x[foil], res["Re"][0][foil] / 1e3, color=c, lw=2)
    for v in (cfg["constraints"]["chord_min"], cfg["constraints"]["chord_max"]):
        ax[0].axhline(v * 1000, color=INK2, lw=0.8)
    ax[2].axhline(cfg["constraints"]["t_min"] * 1000, color=INK2, lw=0.8)
    ax[2].set_ylim(0, 16)
    ax[4].axhline(1 / 3, color=INK2, lw=0.8)
    ax[0].set(ylabel="Chord [mm]", title="Realistic chord (dotted: ideal BEM)")
    ax[1].set(ylabel="Twist θ [deg]", title="Twist (kept from BEM)")
    ax[2].set(ylabel="$t_{max}$ [mm]", title="Max thickness of airfoil sections (limit 5 mm)")
    ax[3].set(ylabel="α [deg]", title="Angle of attack at the operating λ (dotted: α_des)")
    ax[4].set(ylabel="a [-]", title="Axial induction at the operating λ (line: 1/3)")
    ax[5].set(ylabel="Local Re [×10³]", title="Reynolds number at the operating λ")
    for a in ax:
        a.set_xlabel("r/R [-]")
    ax[0].legend(fontsize=7.5)
    fig.suptitle("Realistic blade and what each section sees at the operating point (λ_des if λ is fixed, else λ of $C_{P,max}$; tip loss)",
                 x=0.01, ha="left")
    fig.tight_layout(); finish(fig, out / "A4_blade_operating.png")
    print(f"6 figures -> {out}")
    if SHOW:
        print("Showing the figures; close the windows to finish.")
        plt.show()


if __name__ == "__main__":
    main()
