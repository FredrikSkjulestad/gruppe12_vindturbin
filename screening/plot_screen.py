"""Figures for the report from the NeuralFoil screening (run after 00_screen.py).
Use --out <folder> to plot a screening that was run with --out.

Reads : screening/results/screen_designs.csv, screen_ranking.csv
Writes: screening/results/fig_screen_top20.png      best Cp at lambda 5.4 per airfoil, top 20
        screening/results/fig_screen_distribution.png  best Cp of all ranked airfoils
        screening/results/fig_screen_heatmap.png    Cp vs alpha offset, top 15
"""
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
RES = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else HERE / "results"
TOP, REF = "#2a78d6", "#eb6834"          # top 5 / e68 reference
GREY, INK, MUTED = "#a8a7a1", "#0b0b0b", "#52514e"
plt.rcParams.update({"font.size": 10, "axes.edgecolor": MUTED, "axes.labelcolor": INK,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False,
                     "axes.spines.right": False, "savefig.dpi": 200, "savefig.bbox": "tight"})

rank = pd.read_csv(RES / "screen_ranking.csv")
des = pd.read_csv(RES / "screen_designs.csv")
lam = rank.lambda_des.iloc[0]

# ---------------------------------------------------------------- 1. top 20 dot plot
t = rank.head(20).iloc[::-1]
if "e68" not in set(t.airfoil):
    t = pd.concat([rank[rank.airfoil == "e68"], t])
fig, ax = plt.subplots(figsize=(6.2, 5.6))
col = [TOP if r <= 5 else (REF if a == "e68" else GREY) for a, r in zip(t.airfoil, t["rank"])]
y = np.arange(len(t))
ax.hlines(y, t.Cp_at_lam_des_TL.min() - 0.0003, t.Cp_at_lam_des_TL, color="#e4e3df", lw=1.5, zorder=1)
ax.scatter(t.Cp_at_lam_des_TL, y, s=50, c=col, zorder=2, edgecolor="white", linewidth=1.5)
ax.set_yticks(y, [f"{int(r)}. {a}" for a, r in zip(t.airfoil, t["rank"])])
for yi, (cp, r) in enumerate(zip(t.Cp_at_lam_des_TL, t["rank"])):
    if r <= 5:
        ax.text(cp + 0.00006, yi, f"{cp:.4f}", va="center", fontsize=8.5, color=INK)
ax.set_xlabel(f"$C_p$ at $\\lambda$ = {lam:g} with tip loss (best $\\alpha_{{des}}$ per airfoil)")
ax.grid(axis="x", color="#ecebe7", lw=0.8)
ax.set_axisbelow(True)
ax.set_title(f"NeuralFoil screening: top 20 of {len(rank)} airfoils", loc="left", color=INK)
ax.text(0, -0.15, "Blue: top 5, recalculated with XFOIL. Orange: e68, the winner of the first round.",
        transform=ax.transAxes, fontsize=8.5, color=MUTED)
fig.savefig(RES / "fig_screen_top20.png")
plt.close(fig)

# ---------------------------------------------------------------- 2. distribution of all airfoils
fig, ax = plt.subplots(figsize=(6.2, 3.4))
cp = rank.Cp_at_lam_des_TL
lo = 0.40
n_out = int((cp < lo).sum())
ax.hist(cp[cp >= lo], bins=np.arange(lo, cp.max() + 0.002, 0.002), color=GREY, edgecolor="white", linewidth=1)
cut = rank.Cp_at_lam_des_TL.iloc[min(4, len(rank) - 1)]                # 5th best (or the last, for short lists)
ax.axvline(cut, color=TOP, lw=1.5)
ax.annotate(f"top {min(5, len(rank))}: $C_p \\geq$ {cut:.4f}", xy=(cut, ax.get_ylim()[1] * 0.85), xytext=(0.418, ax.get_ylim()[1] * 0.85),
            va="center", fontsize=8.5, color=INK, arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8))
ax.set_xlim(lo, 0.458)
ax.set_xlabel(f"Best $C_p$ at $\\lambda$ = {lam:g} with tip loss")
ax.set_ylabel("Number of airfoils")
ax.set_title(f"All {len(rank)} screened airfoils", loc="left", color=INK)
ax.text(0, -0.28, f"{n_out} airfoils with $C_p$ < {lo} not shown.", transform=ax.transAxes, fontsize=8.5, color=MUTED)
fig.savefig(RES / "fig_screen_distribution.png")
plt.close(fig)

# ---------------------------------------------------------------- 3. heatmap Cp vs alpha offset
names = list(rank.head(15).airfoil)
h = (des[des.airfoil.isin(names)].pivot(index="airfoil", columns="alpha_offset", values="Cp_at_lam_des_TL")
     .reindex(names))
h = h[sorted(h.columns, reverse=True)]
fig, ax = plt.subplots(figsize=(7.4, 5.4))
vmin = np.nanpercentile(h.values, 5)
im = ax.imshow(h.values, cmap="Blues", vmin=vmin, vmax=np.nanmax(h.values), aspect="auto")
ax.set_xticks(range(h.shape[1]), [f"{c:+.1f}" for c in h.columns], fontsize=8.5)
ax.set_yticks(range(h.shape[0]), [f"{i + 1}. {n}" for i, n in enumerate(names)])
for i in range(h.shape[0]):
    j = int(np.nanargmax(h.values[i]))
    ax.scatter(j, i, s=26, facecolor="none", edgecolor=REF, linewidth=1.6)
ax.set_xlabel("$\\Delta\\alpha = \\alpha_{des} - \\alpha_{opt}$ [deg]")
ax.spines[["left", "bottom"]].set_visible(False)
cb = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
cb.set_label(f"$C_p$ at $\\lambda$ = {lam:g} with tip loss")
cb.outline.set_visible(False)
ax.set_title("Cp against design angle offset, top 15 (circle = best offset)", loc="left", color=INK)
fig.savefig(RES / "fig_screen_heatmap.png")
plt.close(fig)
print("figures written to", RES)
