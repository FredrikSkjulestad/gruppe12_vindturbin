"""Check bem.py against the earlier GOE 227 work, using the SAME polars QBlade used.

(a) Assignment 3: QBlade/XFOIL polars Re 100k-250k (25k step) plus the 208k polar, as in Ass3.py's folder -> Step 2 + Step 3 at lambda = 6, N = 15.
    Reference (A3 report / project note): Re 208 290 -> 145 160 -> 136 621, alpha_opt 6.00,
    CL 1.4770, CD 0.0207, Cp 0.5245, CT 0.8847, chord column of the A4 workbook Table 2.
(b) Assignment 4: blade "Ass4_blade_v2" (workbook Table 3 with the 8 outer chords raised to 40 mm),
    QBlade 360 deg polar at Re 208 000 on every section (as in the QBlade project), cylinder CD = 1.2.
    Reference: QBlade Cp(lambda) exports, Cp_max 0.427 @ 5.6 with tip loss, 0.480 @ 5.4 without.
Run from the wind_blade folder:  python validation/validate_goe227.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import bem
from xfoil_runner import _read_pol

cfg = bem.load_config()
out = HERE / "output"; out.mkdir(exist_ok=True)

# ---------------------------------------------------------------- (a) Assignment 3
raw = {}
for f in sorted((HERE / "qblade_polars").glob("goe227_Re0.*.txt")):
    re = float(f.stem.split("Re")[1]) * 1e6
    raw[re] = _read_pol(f)
pol = bem.PolarSet.from_raw("goe227", raw, cfg)
conv = bem.converge_re(pol, 6.0, 0.0, cfg)
blade = bem.design_blade(6.0, conv, cfg)
perf = bem.design_point_perf(blade, 6.0, cfg)
ref_chord = np.array([0.04897, 0.08584, 0.0848, 0.07483, 0.06469, 0.05617, 0.04928, 0.04374, 0.03922,
                      0.03551, 0.0324, 0.02978, 0.02754, 0.0256, 0.02391])
ref_theta = np.array([46.46, 33.36, 24, 17.69, 13.37, 10.3, 8.03, 6.29, 4.93, 3.83, 2.93, 2.18, 1.54, 0.99, 0.52])
lines = ["(a) Assignment 3 reproduction (QBlade polars)",
         f"  Re history      : {' -> '.join(f'{r:,.0f}' for r in conv['re_hist'])}",
         f"  alpha_opt       : {conv['alpha_des']:.2f} deg   (ref 6.00)",
         f"  CL, CD          : {conv['CL']:.4f}, {conv['CD']:.4f}   (ref 1.4770, 0.0207)",
         f"  Cp, CT          : {perf['Cp_design']:.4f}, {perf['Ct_design']:.4f}   (ref 0.5245, 0.8847)",
         f"  max |chord err| : {np.abs(blade.chord.values - ref_chord).max()*1000:.2f} mm",
         f"  max |twist err| : {np.abs(blade.theta_deg.values - ref_theta).max():.2f} deg"]

# ---------------------------------------------------------------- (b) Assignment 4
plr = pd.read_csv(HERE / "qblade_polars" / "goe227_Re0.208_360_V.plr", sep=r"\s+", skiprows=18,
                  names=["alpha", "CL", "CD", "CM", "a", "b", "c"], engine="python")
plr = plr.apply(pd.to_numeric, errors="coerce").dropna()
grid = np.arange(-180, 180.001, 0.25)          # QBlade's alpha grid is non-uniform: resample
qpol = bem.PolarSet("goe227_qblade", np.array([208000.0]), grid,
                    np.interp(grid, plr.alpha, plr.CL)[None, :], np.interp(grid, plr.alpha, plr.CD)[None, :])
st = pd.DataFrame(dict(r=[0.03] + list(blade.r.values[1:]) + [0.45],
                       chord=[0.048] + list(np.maximum(ref_chord[1:], 0.04)) + [0.04],
                       theta_deg=[0.0] + list(ref_theta[1:]) + [ref_theta[-1]],
                       foil=["cyl"] + ["airfoil"] * 15))
pan = bem.panels(st, cfg["performance"]["n_panels"], 0.45, 0.03)
lams = np.round(np.arange(1.0, 12.01, 0.1), 2)
res = {tl: bem.bem_sweep(pan, qpol, lams, cfg, tl) for tl in (False, True)}

def read_qb(f):
    d = pd.read_csv(f, sep="\t", skiprows=3, header=None).replace("END", np.nan).astype(float)
    return d
qcp = read_qb(HERE / "qblade_curves" / "TipLoss_Cp_Ass4_graph.txt")
qct = read_qb(HERE / "qblade_curves" / "TipLoss_Ct_Ass4_graph.txt")
fig, ax = plt.subplots(1, 2, figsize=(11, 4))
for tl, col, lab, k in [(False, "#2a78d6", "no tip loss", 0), (True, "#eb6834", "Prandtl tip loss", 2)]:
    s = bem.summarise(res[tl], 0.95)
    q = qcp.iloc[:, [k, k + 1]].dropna().values
    iq = np.argmax(q[:, 1])
    lines.append(f"(b) {lab:17s}: this code Cp_max {s['Cp_max']:.3f} @ {s['lam_at_Cp_max']:.1f}   "
                 f"QBlade {q[iq,1]:.3f} @ {q[iq,0]:.1f}")
    ax[0].plot(q[:, 0], q[:, 1], color=col, lw=1.5, ls="--", label=f"QBlade, {lab}")
    ax[0].plot(res[tl]["lam"], res[tl]["Cp"], color=col, lw=2, label=f"bem.py, {lab}")
    qt = qct.iloc[:, [k, k + 1]].dropna().values
    ax[1].plot(qt[:, 0], qt[:, 1], color=col, lw=1.5, ls="--")
    ax[1].plot(res[tl]["lam"], res[tl]["Ct"], color=col, lw=2)
ax[0].set(xlabel="Tip speed ratio λ [-]", ylabel="$C_P$ [-]", ylim=(0, 0.6), title="Ass4_blade_v2, same QBlade polar")
ax[1].set(xlabel="Tip speed ratio λ [-]", ylabel="$C_T$ [-]", ylim=(0, 1.6))
ax[0].legend(frameon=False, fontsize=8)
for a in ax: a.grid(alpha=.3)
fig.tight_layout(); fig.savefig(out / "validation_ass4_qblade.png", dpi=150)
(out / "validation_report.txt").write_text("\n".join(lines), encoding="utf-8")
print("\n".join(lines))
